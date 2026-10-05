#!/usr/bin/env python3
"""Stepwise editing benchmark against camel-jbang-mcp (camel mcp --http), using the shared authoring tools
from CAMEL-24695.

The model gets the shared authoring set (camel_catalog_doc, camel_catalog_find, camel_validate_source,
camel_get_files, camel_write_file, camel_run, camel_control, camel_get_log, camel_get_errors,
camel_eval_expression, camel_error_diagnose) plus a few catalog tools, and a short neutral system
prompt. The harness starts the integration once with camel_run (dev mode) before step 1, then sends the
8 requests one at a time. Scoring: files on disk, log via camel_get_log,
errors via camel_get_errors, diff size, reference checkpoint after each step.

Env: BENCH_MODEL (ollama model), MCP_URL (default http://127.0.0.1:9090/mcp), BENCH_TAG (results folder name),
BENCH_STEPS (the steps file, default steps.json),
BENCH_TOOL_CALLS (max tool calls per step, default 12).
"""
import difflib, json, os, re, subprocess, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient  # noqa: E402

MODEL = os.environ.get("BENCH_MODEL", "qwen3.6:35b-a3b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:9090/mcp")
HERE = os.path.dirname(os.path.abspath(__file__))
TAG = os.environ.get("BENCH_TAG", "mcp-" + MODEL.replace(":", "_").replace("/", "_"))
OUT = os.path.join(HERE, "stepwise", TAG)
MAX_TOOL_CALLS = int(os.environ.get("BENCH_TOOL_CALLS", "20"))
# the conversation grows over an example's steps (logs with stack traces are the bulk); at 32k a long example ran out
# of context and the model stopped after a few words without a tool call (round 3, circuit-breaker steps 2-3)
NUM_CTX = int(os.environ.get("BENCH_NUM_CTX", "65536"))
# how many log records a step is scored on. A step that provokes failures on purpose (errors_ok) fills the window
# with its own expected errors, and the line the check looks for scrolls out of it while sitting in the run log
LOG_WINDOW = int(os.environ.get("BENCH_LOG_WINDOW", "400"))
# round 2: BENCH_REFERENCE=1 skips the model and applies each step's reference files instead, to check the steps file itself
REFERENCE = os.environ.get("BENCH_REFERENCE") == "1"
# CAMEL-24834: before each step, ask camel_runtime_tool_groups what the app has and offer its groups' tools and guidance,
# as the AI panel of the camel-jbang views does for a local model (the tool list changes only when the fingerprint does)
TOOL_GROUPS = os.environ.get("BENCH_TOOL_GROUPS") == "1"
TOOL_RESULT_CAP = 6000

SHARED = ["camel_catalog_doc", "camel_catalog_find", "camel_catalog_sample", "camel_validate_source", "camel_get_files", "camel_write_file",
          "camel_edit_file",
          "camel_run", "camel_control", "camel_get_log", "camel_get_errors", "camel_eval_expression", "camel_error_diagnose"]
EXTRA = ["camel_catalog_docs", "camel_component_properties", "camel_configuration_validate"]
# CAMEL-24834 tool-group experiment: BENCH_EXTRA_TOOLS=camel_execute_sql,camel_get_datasources adds a group to the set
EXTRA += [t for t in os.environ.get("BENCH_EXTRA_TOOLS", "").split(",") if t]

SYSTEM = (
    "You are an Apache Camel assistant helping a developer edit a running Camel integration through the Camel MCP server.\n\n"
    "The project directory is {directory}. The integration {name} is already running from it in dev mode: files you write are "
    "reloaded automatically.\n\n"
    "Guidelines:\n"
    "- To edit: camel_get_files (directory, optionally file) to read, then camel_edit_file (directory, file, find, replace) to "
    "change one part of it: find is the lines as they stand in the file and must occur once. camel_write_file (directory, file, "
    "content) writes a whole file, for a new one. Invalid YAML or properties is refused with errors: fix them "
    "(camel_catalog_doc has the option names) and try again.\n"
    "- camel_validate_source checks content before writing; camel_eval_expression checks a simple expression; camel_get_log and "
    "camel_get_errors show what the running integration did after a reload.\n"
    "- camel_catalog_sample (name) shows a validated YAML sample of an EIP and where it goes (top level or step): use it "
    "before writing an EIP you have not written in this file yet, and after a 'not defined in the schema' error.\n"
    "- Simple: functions inside ${...}, operators between them: ${header.a} == 'b', ${body} ?: 'none'.\n"
    "- Never stop, kill or restart the integration unless asked.\n"
    "- If a tool call returns an error, do not repeat it with the same arguments; say what failed and what to try.\n"
    "- Be concise; when done, say in one or two sentences what you changed.\n"
)


def ollama_chat(messages, tools):
    # thinking off, as the Camel CLI's own Ollama client sends and as the one-shot harness does: with it on, four of
    # 33 HTTP steps in series s5 spent 4-8 minutes and 12-28k tokens and answered nothing (CAMEL-24886)
    body = json.dumps({"model": MODEL, "messages": messages, "tools": tools, "stream": False, "think": False,
                       "options": {"temperature": 0.2, "num_ctx": NUM_CTX}}).encode()
    req = urllib.request.Request(HOST + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.load(r)
    return data, time.time() - t0


def to_ollama_tools(mcp_tools, names):
    byname = {t["name"]: t for t in mcp_tools}
    out = []
    for n in names:
        t = byname.get(n)
        if not t:
            print(f"WARNING: tool {n} not exposed by the server", file=sys.stderr)
            continue
        out.append({"type": "function", "function": {"name": n, "description": t.get("description") or "",
                                                      "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}})
    return out


def read(path):
    try:
        return open(path).read()
    except FileNotFoundError:
        return ""


def jcall(mcp, name, args):
    out = mcp.call(name, args)
    try:
        return json.loads(out), out
    except Exception:
        return None, out


def log_lines(mcp, name, limit=40):
    data, raw = jcall(mcp, "camel_get_log", {"name": name, "limit": limit})
    if isinstance(data, dict):
        for k in ("lines", "records", "entries"):
            if k in data:
                return data[k]
    if isinstance(data, list):
        return data
    return []


def tod(t):
    """A log record's time as seconds of the day; None when it cannot be read."""
    try:
        t = (t or "").split("T")[-1].split(" ")[-1]
        h, m, sec = t.split(":")[:3]
        return int(h) * 3600 + int(m) * 60 + float(sec)
    except Exception:
        return None


def is_reload(l):
    m = (l.get("message") or l.get("msg") or "")
    return "Routes reloaded summary" in m or "Error reloading routes" in m or "Reloading properties" in m


def reload_key(l):
    return (l.get("time") or l.get("timestamp") or "") + "|" + (l.get("message") or l.get("msg") or "")[:80]


def error_key(l):
    return (l.get("time") or l.get("timestamp") or "") + "|" + (l.get("message") or l.get("msg") or "")[:120]


INFRA_TIMEOUT = int(os.environ.get("BENCH_INFRA_TIMEOUT", "300"))    # seconds to wait for `camel infra` services


def infra_start(services):
    """Start the services the example needs with `camel infra run <svc> --background` and wait until each answers.

    Stopped first, so every pass starts against an empty database. A service kept running between passes would carry
    its rows over, and then a step that changes a row passes on what the pass before it left rather than on the work
    of the model: step 3 sets C-207 to NL, and the next pass would find it already NL. Postgres takes about 80 s to
    come up, which is the price of that. The runner stops them when the whole run is over.
    """
    for svc in services:
        subprocess.run(["camel", "infra", "stop", svc], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for svc in services:
        subprocess.run(["camel", "infra", "run", svc, "--background"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data, deadline = {}, time.time() + INFRA_TIMEOUT
    for svc in services:
        while time.time() < deadline:
            out = subprocess.run(["camel", "infra", "get", svc, "--json"], capture_output=True, text=True).stdout
            m = re.search(r"\{.*\}", out, re.S)
            if m:
                try:
                    data[svc] = json.loads(m.group(0))
                    break
                except json.JSONDecodeError:
                    pass
            time.sleep(5)
        else:
            data[svc] = {"error": f"{svc} did not come up within {INFRA_TIMEOUT}s"}
    return data


def apply_reference(project, cfg, reference, mcp, name, before=None):
    """Write a step's reference files, all of them, as one save.

    They used to be written in two goes, the properties first and the route once that reload had landed, because dev
    mode reloaded the routes of a change before its properties, so a route written in the same poll as the property it
    uses failed to start. CAMEL-25041 reloads one save as one batch with the properties applied first, so one go is
    right again -- and better: two writes two seconds apart reloaded the app twice, and an HTTP call in flight across
    the second reload was answered 404 by a rest route that was being rebuilt (ref12, connect-http-client step 1).
    """
    for fname in reference:
        os.makedirs(os.path.dirname(os.path.join(project, fname)) or project, exist_ok=True)
        with open(os.path.join(project, fname), "w") as f:
            f.write(reference[fname])
    return len(reference)


def error_snapshot(mcp, name):
    """The ERROR records in the log window and the error file's count, taken before a step (round 2).

    Also the INFO and WARN records already in the window: the window holds 150 records and spans the step before,
    so a log_not_regex would otherwise fail a step for output that the previous step's route produced.
    """
    lines = log_lines(mcp, name, LOG_WINDOW)
    records = {error_key(l) for l in lines if isinstance(l, dict) and (l.get("level") or "").upper() == "ERROR"}
    reloads = {reload_key(l) for l in lines if isinstance(l, dict) and is_reload(l)}
    before_msgs = {error_key(l) for l in lines
                   if isinstance(l, dict) and (l.get("level") or "").upper() in ("INFO", "WARN")}
    data, _ = jcall(mcp, "camel_get_errors", {"name": name})
    count = len(data.get("errors", []) or []) if isinstance(data, dict) else 0
    return records, count, reloads, before_msgs


def probe(pr):
    """One HTTP request of a step check: {"method", "url", "headers", "body", "expect_status", "body_regex"}; the
    server may still be settling after the reload, so the request is retried a few times until the expected status."""
    method = pr.get("method", "GET"); url = pr["url"]; want = int(pr.get("expect_status", 200))
    out = {"url": url, "method": method, "ok": False, "status": None, "body": ""}
    for _ in range(6):
        try:
            data = pr["body"].encode() if pr.get("body") is not None else None
            req = urllib.request.Request(url, data=data, method=method, headers=pr.get("headers") or {})
            with urllib.request.urlopen(req, timeout=8) as r:
                out["status"], out["body"] = r.status, r.read().decode(errors="replace")[:600]
        except urllib.error.HTTPError as e:
            out["status"], out["body"] = e.code, e.read().decode(errors="replace")[:600]
        except Exception as e:
            out["status"], out["body"] = None, str(e)[:200]
        # the status alone is not enough: right after a reload the previous route may still answer 200 with its own
        # body, and that is not the answer the step asks for -- retry until the body matches too
        if out["status"] == want and body_matches(pr.get("body_regex"), out["body"]):
            break
        time.sleep(2)
    out["ok"] = out["status"] == want and body_matches(pr.get("body_regex"), out["body"])
    return out


def body_matches(rx, body):
    """The check is about what the route answers, not how it spaces it: a pretty printed JSON body is the same
    answer as a compact one, so the regex is tried against the text and against the body re-serialized compactly."""
    if not rx:
        return True
    if re.search(rx, body or "", re.S):
        return True
    try:
        compact = json.dumps(json.loads(body), separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return False
    return re.search(rx, compact, re.S) is not None


def score(step, project, cfg, mcp, name, before):
    chk = step["check"]
    route = read(os.path.join(project, cfg["route_file"])); props = read(os.path.join(project, cfg.get("props_file", "application.properties")))
    result = {"file_ok": True, "props_ok": True, "log_ok": True, "errors": 0}
    if chk.get("file_regex") and not re.search(chk["file_regex"], route):
        result["file_ok"] = False
    if chk.get("file_regex2") and not re.search(chk["file_regex2"], route):
        result["file_ok"] = False
    if chk.get("file_not_regex") and re.search(chk["file_not_regex"], route):
        result["file_ok"] = False
    if chk.get("props_regex") and not re.search(chk["props_regex"], props):
        result["props_ok"] = False
    # round 2: on macOS the JDK WatchService polls about every 10 s, so a dev-mode reload lands up to 10 s after the
    # write; wait for a reload record newer than the step's snapshot (up to 25 s), then the example's own wait
    seen_reloads = before.get("reload_records") or set()
    reload_at = None
    for _ in range(12):
        fresh_reloads = [l for l in log_lines(mcp, name, LOG_WINDOW)
                         if isinstance(l, dict) and is_reload(l) and reload_key(l) not in seen_reloads]
        if fresh_reloads:
            # the reload this step caused: what the step forbids is only forbidden from here on, whatever the route
            # logged while the model was still writing (the step before it may have been the one provoking it)
            # the last of them: a model that wrote twice in one step is judged on the state it left behind
            times = [t for t in (tod(l.get("time") or l.get("timestamp")) for l in fresh_reloads) if t is not None]
            reload_at = max(times) if times else None
            break
        time.sleep(2)
    # CAMEL-24886: probes are the README's curl: an HTTP request after the reload, its status and body checked
    result["probes"] = [probe(pr) for pr in (chk.get("probes") or [])]
    if any(not pr["ok"] for pr in result["probes"]):
        result["log_ok"] = False
    time.sleep(cfg["wait_seconds"])
    # (after the wait: a file the app writes on the reload, an outbox or an archive, exists only then)
    # round 2: other files of the project (a Java bean, beans.yaml, a stylesheet, a dropped data file)
    for fname, rx in (chk.get("files") or {}).items():
        # by path, else by name anywhere in the project (a class the model put under src/main/java is the same class)
        content = read(os.path.join(project, fname))
        if not content:
            for root, dirs, files in os.walk(project):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if os.path.basename(fname) in files:
                    content = read(os.path.join(root, os.path.basename(fname)))
                    break
        if not re.search(rx, content):
            result["file_ok"] = False
    lines = log_lines(mcp, name, LOG_WINDOW)
    def lvl(l): return (l.get("level") or "").upper()
    # a multi-line message (a pretty-printed body) comes as one record with a detail block: match on both
    def msg(l): return (l.get("message") or l.get("msg") or "") + ("\n" + l["detail"] if l.get("detail") else "")
    recent = [l for l in lines if isinstance(l, dict) and lvl(l) in ("INFO", "WARN")]
    msgs = [msg(l) for l in recent]
    # round 2: log_regex may be a list (all must match), or absent (a step with nothing to see in the log)
    regexes = chk.get("log_regex")
    regexes = [] if regexes is None else (regexes if isinstance(regexes, list) else [regexes])
    matched = []
    for rx in regexes:
        found = [m for m in msgs if re.search(rx, m, re.S)]
        if len(found) < chk.get("min_log", 1):
            result["log_ok"] = False
        matched = found if not matched else matched
    # only what this step produced: the window spans the step before, whose route may legitimately have logged
    # what this step forbids (a circuit breaker step forbids ConnectException, which the step before it provokes)
    seen_msgs = before.get("log_records") or set()

    def after_reload(l):
        if reload_at is None:
            return True
        t = tod(l.get("time") or l.get("timestamp"))
        return t is None or t >= reload_at
    fresh = [msg(l) for l in recent if error_key(l) not in seen_msgs and after_reload(l)]
    if chk.get("log_not_regex") and any(re.search(chk["log_not_regex"], m, re.S) for m in fresh):
        result["log_ok"] = False
    if chk.get("interval_min") and len(matched) >= 2:
        ts = [l.get("time") or l.get("timestamp") or "" for l in recent if re.search(regexes[0], msg(l), re.S)][:2]
        try:
            if abs(tod(ts[0]) - tod(ts[1])) < chk["interval_min"]:
                result["log_ok"] = False
        except Exception:
            pass
    # round 2: errors are counted per step (the log window and the error file keep an earlier step's stack traces)
    seen = before.get("error_records") or set()
    result["errors"] = sum(1 for l in lines if isinstance(l, dict) and lvl(l) == "ERROR" and error_key(l) not in seen)
    data, _ = jcall(mcp, "camel_get_errors", {"name": name})
    if isinstance(data, dict):
        errs = data.get("errors", []) or []
        result["errors"] += max(0, len(errs) - before.get("error_count", 0))
        # what they were, not just how many: a step that fails on errors alone cannot be judged from a count
        result["error_detail"] = [str(e)[:300] for e in errs[before.get("error_count", 0):]][:5]
    diff = list(difflib.unified_diff(before["route"].splitlines(), route.splitlines(), lineterm="", n=0))
    diffp = list(difflib.unified_diff(before["props"].splitlines(), props.splitlines(), lineterm="", n=0))
    result["changed_lines"] = sum(1 for l in diff + diffp if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---")))
    # round 2: a step may expect errors (the supplier throwing nine times) or tolerate them
    errors_fine = result["errors"] == 0 or bool(chk.get("errors_ok"))
    if chk.get("min_errors") and result["errors"] < chk["min_errors"]:
        errors_fine = False
    # ok_final: the end state is right (files and log), whatever happened on the way; ok also needs no errors
    result["ok_final"] = result["file_ok"] and result["props_ok"] and result["log_ok"]
    result["ok"] = result["ok_final"] and errors_fine
    result["log_sample"] = msgs[:5]
    return result, route, props


def main():
    cfg = json.load(open(os.path.join(HERE, os.environ.get("BENCH_STEPS", "steps.json"))))
    project = cfg["project"]
    if not os.path.isabs(project):
        project = os.path.join(HERE, project)
    os.makedirs(OUT, exist_ok=True)
    log = open(os.path.join(OUT, "run.log"), "a")
    mcp = McpClient(MCP_URL); mcp.initialize(); all_tools = mcp.list_tools()
    tools = to_ollama_tools(all_tools, SHARED + EXTRA)
    print(f"tools: {[t['function']['name'] for t in tools]}", file=log, flush=True)

    proc = None
    peer = None
    if cfg.get("infra"):
        # the services the example connects to, as its README starts them: the sql example's postgres. Left running
        # when the pass ends, so the next pass of the same example does not pay the startup again (about 80 s); the
        # runner stops them when the whole run is over
        t0 = time.time()
        data = infra_start(cfg["infra"])
        print(f"camel infra run {' '.join(cfg['infra'])} -> {json.dumps(data)[:300]} ({time.time() - t0:.0f}s)",
              file=log, flush=True)
        for svc, d in data.items():
            if isinstance(d, dict) and d.get("error"):
                print(f"ABORT: {d['error']}", file=log, flush=True)
                raise SystemExit(f"{svc} did not come up")
    if cfg.get("peer"):
        # CAMEL-24886: a second app the example talks to (the stock API behind a client), from its own directory
        pd = os.path.join(HERE, cfg["peer"]["project"]); pname = cfg["peer"]["name"]
        peer_out = open(os.path.join(OUT, "peer-run.out"), "w")
        peer = subprocess.Popen(["camel", "run", "--source-dir=" + pd, "--name=" + pname, "--logging-color=false"],
                                stdout=peer_out, stderr=subprocess.STDOUT, cwd=pd)
        for _ in range(60):
            time.sleep(1)
            if "Routes startup" in read(os.path.join(OUT, "peer-run.out")) or peer.poll() is not None:
                break
        time.sleep(2)
        print(f"peer camel run --source-dir -> pid {peer.pid} name {pname}", file=log, flush=True)
    if cfg.get("source_dir"):
        # round 2: camel run --source-dir watches the whole directory, so a bean file or a Java class the model adds
        # later is part of the app (the MCP camel_run starts with the files of the moment, and a restart replays
        # them); the MCP tools find the integration by name
        name = os.path.basename(project)
        run_out = open(os.path.join(OUT, "camel-run.out"), "w")
        proc = subprocess.Popen(["camel", "run", "--source-dir=" + project, "--dev", "--name=" + name, "--logging-color=false"],
                                stdout=run_out, stderr=subprocess.STDOUT, cwd=project)
        for _ in range(60):
            time.sleep(1)
            if "Routes startup" in read(os.path.join(OUT, "camel-run.out")) or proc.poll() is not None:
                break
        time.sleep(3)
        print(f"camel run --source-dir -> pid {proc.pid} name {name}", file=log, flush=True)
    else:
        # start the integration once, in dev mode, through the MCP server
        data, raw = jcall(mcp, "camel_run", {"directory": project})
        print(f"camel_run -> {raw[:300]}", file=log, flush=True)
        name = (data or {}).get("name") or os.path.basename(project)
        time.sleep(6)

    base_system = SYSTEM.replace("{directory}", project).replace("{name}", name)
    messages = [{"role": "system", "content": base_system}]
    groups_fp = None
    results = []
    try:
        for step in cfg["steps"]:
            sid = step["id"]
            if TOOL_GROUPS and not REFERENCE:
                data, raw = jcall(mcp, "camel_runtime_tool_groups", {"nameOrPid": name})
                if isinstance(data, dict) and data.get("fingerprint") != groups_fp:
                    groups_fp = data.get("fingerprint")
                    extra = [t for g in data.get("groups") or [] for t in g.get("tools") or []]
                    tools = to_ollama_tools(all_tools, SHARED + EXTRA + [t for t in extra if t not in SHARED + EXTRA])
                    guidance = [g["guidance"] for g in data.get("groups") or [] if g.get("guidance")]
                    messages[0]["content"] = base_system + (
                        "\nThe running integration:\n" + "".join("- " + g + "\n" for g in guidance) if guidance else "")
                print(f"step{sid}: tool groups {groups_fp} -> {raw[:300]}", file=log, flush=True)
            before = {"route": read(os.path.join(project, cfg["route_file"])), "props": read(os.path.join(project, cfg.get("props_file", "application.properties")))}
            before["error_records"], before["error_count"], before["reload_records"], before["log_records"] \
                = error_snapshot(mcp, name)
            trace = open(os.path.join(OUT, f"step{sid}.trace.jsonl"), "w")
            messages.append({"role": "user", "content": step["request"]})
            calls = 0; tokens = 0; t0 = time.time(); writes = 0; refused = 0; answer = ""
            if REFERENCE:
                # the reference files stand in for the model's edits; the checks then score the steps file itself
                writes += apply_reference(project, cfg, step.get("reference") or {}, mcp, name, before)
                answer = "(reference)"
            while not REFERENCE:
                try:
                    data, secs = ollama_chat(messages, tools)
                except Exception as e:
                    trace.write(json.dumps({"error": str(e)}) + "\n"); break
                msg = data["message"]; tokens += data.get("eval_count", 0)
                trace.write(json.dumps({"secs": round(secs, 1), "eval": data.get("eval_count"), "prompt_eval": data.get("prompt_eval_count"),
                                        "tool_calls": msg.get("tool_calls"), "content": (msg.get("content") or "")[:500]}) + "\n"); trace.flush()
                messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg.get("tool_calls")})
                if msg.get("tool_calls") and calls < MAX_TOOL_CALLS:
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]; calls += 1
                        args = fn.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        args = dict(args)
                        if fn["name"] in ("camel_get_files", "camel_write_file", "camel_edit_file", "camel_validate_source",
                                          "camel_run") and "directory" not in args:
                            args["directory"] = project
                        if fn["name"] in ("camel_get_log", "camel_get_errors", "camel_control", "camel_eval_expression") and "name" not in args:
                            args["name"] = name
                        # the runtime tools take nameOrPid; the AI panel always means the selected integration, and
                        # without it they fail on "multiple processes running" when a peer app runs beside it
                        if fn["name"].startswith("camel_runtime_") and not args.get("nameOrPid"):
                            args["nameOrPid"] = name
                        if fn["name"] in ("camel_write_file", "camel_edit_file"):
                            writes += 1
                        try:
                            out = mcp.call(fn["name"], args)
                        except Exception as e:
                            out = "ERROR: " + str(e)
                        if fn["name"] in ("camel_write_file", "camel_edit_file") and ('"invalid"' in out
                                or '"not-found"' in out or '"ambiguous"' in out or out.startswith("ERROR")):
                            refused += 1
                        out = out[:TOOL_RESULT_CAP]
                        trace.write(json.dumps({"tool": fn["name"], "args": {k: (v if k != "content" else v[:1500]) for k, v in args.items()}, "result": out[:800]}) + "\n"); trace.flush()
                        messages.append({"role": "tool", "content": out, "tool_name": fn["name"]})
                    continue
                answer = msg.get("content") or ""
                break
            if cfg.get("restart_each_step") or step.get("restart"):
                # round 2: the README's "run after each step" where a reload is not enough: a new or changed Java
                # class is not compiled on a reload, so the step says restart and the harness restarts (the request
                # says so too, a model that restarts itself is fine)
                data, raw = jcall(mcp, "camel_control", {"name": name, "action": "restart"})
                print(f"step{sid}: camel_control restart -> {raw[:200]}", file=log, flush=True)
                if isinstance(data, dict) and data.get("name"):
                    name = data["name"]
                time.sleep(8)
            res, route_after, props_after = score(step, project, cfg, mcp, name, before)
            res.update({"step": sid, "request": step["request"], "tool_calls": calls, "writes": writes, "refused_writes": refused,
                        "seconds": round(time.time() - t0, 1), "tokens": tokens, "answer": answer[:400]})
            results.append(res)
            with open(os.path.join(OUT, f"step{sid}.after.yaml"), "w") as f:
                f.write(route_after)
            probes = "".join("P" if pr["ok"] else "F" for pr in res.get("probes") or [])
            print(f"step{sid}: ok={res['ok']} file={res['file_ok']} props={res['props_ok']} log={res['log_ok']} errors={res['errors']} "
                  + (f"probes={probes} " if probes else "")
                  + f"changed_lines={res['changed_lines']} calls={calls} writes={writes} refused={refused} secs={res['seconds']} tokens={tokens}", file=log, flush=True)
            trace.close()
            if step.get("reference"):
                for fname in step["reference"]:
                    # a same-named file elsewhere (the model's copy of a Java class under src/main/java) would be a
                    # second class of the same name after the fix: remove it
                    for root, dirs, files in os.walk(project):
                        dirs[:] = [d for d in dirs if not d.startswith(".")]
                        other = os.path.join(root, os.path.basename(fname))
                        if os.path.basename(fname) in files and os.path.abspath(other) != os.path.abspath(os.path.join(project, fname)):
                            os.remove(other)
                apply_reference(project, cfg, step["reference"], mcp, name)
                # the checkpoint write reloads the app too (on macOS up to 10 s later): wait for that reload and let
                # its consumers settle, so the next step's error and log snapshot is taken in a quiet state
                seen = error_snapshot(mcp, name)[2]
                for _ in range(12):
                    time.sleep(2)
                    if any(reload_key(l) not in seen for l in log_lines(mcp, name, LOG_WINDOW) if isinstance(l, dict) and is_reload(l)):
                        break
                time.sleep(6)
                if not res["ok"]:
                    messages.append({"role": "user", "content": "I fixed that step myself; the files now contain the correct version. Continue with the next request."})
            json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    finally:
        data, raw = jcall(mcp, "camel_control", {"name": name, "action": "stop"})
        print(f"camel_control stop -> {raw[:200]}", file=log, flush=True)
        if peer is not None:
            subprocess.run(["camel", "stop", cfg["peer"]["name"]], capture_output=True)
            try:
                peer.wait(timeout=20)
            except Exception:
                peer.kill()
        if proc is not None:
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()
    print(f"DONE passed={sum(1 for r in results if r['ok'])}/{len(results)}", file=log, flush=True)
    log.close()


if __name__ == "__main__":
    main()
