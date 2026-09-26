#!/usr/bin/env python3
"""One-shot benchmark: a local model builds each example from its one-line description, with the Camel MCP
server's catalog and validation tools, in a small agent loop.

Per example:
  round 1..MAX_ROUNDS:
    model may call MCP tools (catalog lookups, YAML validation) up to MAX_TOOL_CALLS times,
    then answers with files in '=== FILE: name ===' format.
    We write the files to <BENCH_OUT>/<name>/attempt<round>/, run validate + camel run, and if it
    fails we feed the validator/run errors back and loop.
Everything (tool calls, timings, tokens) is logged to <BENCH_OUT>/<name>/trace.jsonl.
"""
import glob
import json, os, re, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient  # noqa: E402
from gen_local import write_files, strip_think  # noqa: E402

MODEL = os.environ.get("BENCH_MODEL", "qwen3.6:35b-a3b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.environ.get("BENCH_OUT", "oneshot"))
EXAMPLES_FILE = os.environ.get("BENCH_EXAMPLES", "examples.json")   # examples-intermediate.json for set B
INFRA_TIMEOUT = int(os.environ.get("BENCH_INFRA_TIMEOUT", "300"))    # seconds to wait for `camel infra` services
MAX_ROUNDS = int(os.environ.get("BENCH_ROUNDS", "3"))
MAX_TOOL_CALLS = int(os.environ.get("BENCH_TOOL_CALLS", "10"))
TOOL_RESULT_CAP = 6000

# Tools offered to the model: catalog lookups and validation only. No example catalog
# (that would hand the model the answer), no runtime, security, migration or dependency tools.
ALLOW = re.compile(os.environ.get("BENCH_TOOL_ALLOW",
    r"^camel_(catalog_(doc|find|sample|docs)|validate_source|component_properties|configuration_validate|error_diagnose|eval_expression)$"))

SYSTEM = """You are an AI assistant helping a developer build a small Apache Camel integration that runs
with the Camel CLI (camel-jbang), written in Camel YAML DSL.

Facts about the Camel YAML DSL you must respect:
- A route file is a top-level YAML LIST. Each entry is one of `- route:`, `- from:`, `- beans:`, `- rest:`, `- restConfiguration:`.
- A route has `from:` with `uri:` and `steps:`; each step is a map with one EIP key such as `log:`, `to:`, `setBody:`, `choice:`, `split:`, `aggregate:`, `filter:`, `circuitBreaker:`, `bean:`.
- Expressions are written as `simple: "..."`, `constant: "..."`, `groovy: "..."`, `tokenize: {token: ","}`.
- Java beans must be declared with `- beans:` using `type: "#class:<FullyQualifiedOrSimpleClassName>"` before `bean: {ref: name}`.
- Use a timer or a file consumer as the trigger so the example produces output on its own.

Use the tools to look up component options, EIP options, a validated YAML sample of an EIP you have not used before (camel_catalog_sample), and to validate your YAML before you answer. Then answer with only the
files, each in this exact format, and nothing else:

=== FILE: <filename> ===
<content>

Route files use the extension .camel.yaml. Add application.properties, Java beans, XSLT or input files when needed."""


def ollama_chat(messages, tools):
    # ladder runs (2026-09-19): thinking off, as the Camel CLI's own Ollama client sends ("think": false); the dry run
    # with thinking on spent 460-500 s and 27-29k tokens per spiral and answered nothing three times in four examples.
    # BENCH_THINK=1 restores the round-1 behaviour. num_predict bounds a runaway answer (default 16384).
    req = {"model": MODEL, "messages": messages, "tools": tools, "stream": False,
           "think": os.environ.get("BENCH_THINK", "0") == "1",
           "options": {"temperature": 0.2, "num_ctx": 32768, "num_predict": int(os.environ.get("BENCH_NUM_PREDICT", "16384"))}}
    body = json.dumps(req).encode()
    req = urllib.request.Request(HOST + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.load(r)
    return data, time.time() - t0


def to_ollama_tools(mcp_tools):
    out = []
    for t in mcp_tools:
        if not ALLOW.match(t["name"]):
            continue
        schema = t.get("inputSchema") or {"type": "object", "properties": {}}
        out.append({"type": "function", "function": {
            "name": t["name"], "description": (t.get("description") or "")[:300],
            "parameters": schema}})
    return out


def run_folder(folder, secs, probe, probe_regex=None, checks=None):
    """checks (round 2, the ladder set): the entry's own checks, all visible in the JSON:
    log_regex      list of regexes the run log must match (the behaviour the description promises)
    log_not_regex  list of regexes the run log must not match (the pending order must not reach the warehouse)
    expected_errors regex: error lines that are the example's own behaviour (a retried delivery, a rejected invoice)
    require_files  globs that must exist in the folder after the run (a Java bean, application-prod.properties)
    output_files   [[glob, min count], ...] files the run must have produced (outbox/*.json)"""
    checks = checks or {}
    subprocess.run([os.path.join(HERE, "run_one.sh"), folder, str(secs), probe or ""], check=False)
    v = open(os.path.join(folder, "validate.log")).read()
    r = open(os.path.join(folder, "run.log")).read()
    p = open(os.path.join(folder, "probe.log")).read() if os.path.exists(os.path.join(folder, "probe.log")) else ""
    bad_validate = "exit=1" in v or "Validation error" in v or "no yaml files" in v
    m = re.search(r"Routes startup \(total:(\d+)", r)
    nroutes = int(m.group(1)) if m else 0
    # run 16 on: an ERROR line written by the route's own log step (logger = the route file) is the route's
    # message, not a failure (run 15 groovy logged its rejections at ERROR); a Camel error, an exception or a
    # failed delivery still counts
    errs = [l for l in r.splitlines()
            if re.search(r"ERROR|Exception|Caused by|Unsupported|Unknown|Failed|No bean", l)
            and not (re.search(r"\.(yaml|java):\d+\s", l) and not re.search(r"Exception|Caused by|Failed delivery", l))]
    if checks.get("expected_errors"):
        errs = [l for l in errs if not re.search(checks["expected_errors"], l)]
    # round 2: an example may say what the probe must show (probe_regex); a 404 or an empty body is then not activity
    probe_ok = bool(p.strip()) and (probe_regex is None or re.search(probe_regex, p) is not None)
    activity = len(re.findall(r"\.yaml:\d+ |\.java:\d+ ", r)) > 0 or probe_ok
    if probe_regex is not None and not probe_ok:
        errs_probe = [f"probe did not show the expected result (wanted /{probe_regex}/): " + p.strip()[:300]]
    else:
        errs_probe = []
    if not activity:
        # run 17 on: a log step with its own logName (priority-logger) logs under that name, not the route file;
        # any log line from a logger that is not Camel's own counts as route activity
        for l in r.splitlines():
            m = re.search(r" (INFO|WARN|ERROR|DEBUG) +\d+ --- \[[^\]]*\] (\S+) +: ", l)
            if m and not re.search(r"camel|Camel|MainSupport|Shutdown", m.group(2)):
                activity = True
                break
    # run 14 on: a route that logs from its own file has loaded, even when logging.level.root=WARN (honoured since
    # CAMEL-24701) hides the "Routes startup" line the count is read from
    if nroutes == 0 and activity:
        nroutes = 1
    # the ladder checks: what the description promises, checked on the log and the folder; the feedback names the
    # promised behaviour (the developer's words), never the regex
    errs_check = []
    ran = (not bad_validate) and nroutes > 0 and not errs
    # (only when something went through a route: with no route output at all the "no log output" message below,
    # which names the trigger, is the precise one; dry run 4 read from an orders/ directory that did not exist,
    # three times, and was told the log did not show the behaviour)
    if ran and activity and checks.get("log_regex"):
        # a check is [regex, promise] (the promise is the description's own words); older sets carry a bare regex
        missing = [c[1] if isinstance(c, list) else None
                   for c in checks["log_regex"] if re.search(c[0] if isinstance(c, list) else c, r) is None]
        if missing:
            if all(missing):
                errs_check.append("the log does not show: " + "; ".join(missing))
            else:
                errs_check.append("the log does not show the expected behaviour: " + checks.get("expect", "see the request"))
    for x in checks.get("log_not_regex", []):
        if ran and re.search(x[0] if isinstance(x, list) else x, r):
            errs_check.append("the log shows something the request rules out: " + checks.get("expect", "see the request"))
            break
    for g in checks.get("require_files", []):
        if not glob.glob(os.path.join(folder, g)):
            errs_check.append(f"the project must contain a file matching {g}")
    for f, needle in checks.get("require_text", {}).items():
        path = os.path.join(folder, f)
        if not (os.path.exists(path) and needle in open(path).read()):
            errs_check.append(f"{f} must contain {needle}")
    for g, n in checks.get("output_files", []):
        found = len(glob.glob(os.path.join(folder, g), recursive=True))
        if ran and found < n:
            errs_check.append(f"the run must produce at least {n} file(s) matching {g}, found {found}")
    ok = (not bad_validate) and nroutes > 0 and not errs and activity and not errs_probe and not errs_check
    # CAMEL-24855: the file consumer says when it created the directory it reads from; passed on as evidence when
    # the run failed, since a route reading a directory the project does not have is otherwise silent
    created = re.findall(r"Created starting directory: (\S+) \(it did not exist\)", r)
    if created and not ok:
        errs_check.append("camel run said it created the starting directory " + ", ".join(created)
                          + " (it did not exist): the route read an empty directory the project does not have;"
                          + " the given files are in the project folder itself")
    return ok, v, "\n".join((errs + errs_probe + errs_check)[:15]), nroutes, activity


# --- set B support: services, seed files and hooks (round 2) ---------------------------------------------
# An example may declare:
#   "infra": ["postgres"]        services started with `camel infra run <svc> --background` before the example and
#                                stopped after it; their connection data (`camel infra get <svc> --json`) is handed
#                                to the model in the prompt, as a developer would read it from the same command
#   "seed": true                 files under seed/<example>/ are copied into every attempt folder before the model's
#                                files are written (an OpenAPI spec, sample payloads); the prompt lists them
#   "hint": "..."                one extra sentence in the prompt (a topic name, a server URL); kept in the JSON so
#                                the extra information is visible, not hidden in the harness
#   "pre": "cmd", "post": "cmd"  shell commands run in the harness directory before and after the example
def infra_start(services):
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
                    data[svc] = json.loads(m.group(0)); break
                except json.JSONDecodeError:
                    pass
            time.sleep(5)
        else:
            data[svc] = {"error": f"{svc} did not come up within {INFRA_TIMEOUT}s"}
    return data


def infra_stop(services):
    for svc in services:
        subprocess.run(["camel", "infra", "stop", svc], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def infra_prompt(data):
    lines = []
    for svc, d in data.items():
        keep = {k: v for k, v in d.items() if k in ("endpointUri", "jdbcUrl", "username", "password", "host", "port",
                                                    "beanProperties", "serviceAddress", "brokerUrl", "remoteURI",
                                                    "brokers", "getBootstrapServers")}
        lines.append(f"- {svc}: {json.dumps(keep or d)}")
    return ("\n\nThe following external services are already running on this machine; connect to them with these "
            "details (from `camel infra get`):\n" + "\n".join(lines)) if lines else ""


def seed_files(name, folder):
    src = os.path.join(HERE, "seed", name)
    if not os.path.isdir(src):
        return []
    shutil.copytree(src, folder, dirs_exist_ok=True)
    return sorted(os.path.relpath(os.path.join(r, f), src) for r, _, fs in os.walk(src) for f in fs)


SEED_SHOW_EXT = (".json", ".csv", ".xml", ".xsl", ".groovy", ".txt", ".yaml", ".properties")
SEED_SHOW_MAX = int(os.environ.get("BENCH_SEED_SHOW_MAX", "2500"))   # bytes per shown file


def seed_contents(name, seeded):
    """the content of the small text seed files, one per directory, as the developer would see them"""
    src = os.path.join(HERE, "seed", name)
    shown_dirs, out = set(), []
    for rel in seeded:
        d = os.path.dirname(rel)
        if not rel.endswith(SEED_SHOW_EXT) or d in shown_dirs:
            continue
        path = os.path.join(src, rel)
        if os.path.getsize(path) > SEED_SHOW_MAX:
            continue
        shown_dirs.add(d)
        siblings = [r for r in seeded if os.path.dirname(r) == d and r != rel]
        note = f" (the other files in {d}/ have the same shape)" if siblings and d else ""
        out.append(f"\n\n{rel}{note}:\n```\n{open(path).read().rstrip()}\n```")
    return "".join(out)


def hook(cmd, log):
    if cmd:
        r = subprocess.run(cmd, shell=True, cwd=HERE, capture_output=True, text=True)
        print(f"hook `{cmd}` exit={r.returncode} {r.stdout.strip()[:200]} {r.stderr.strip()[:200]}", file=log, flush=True)


def main():
    examples = json.load(open(os.path.join(HERE, EXAMPLES_FILE)))
    only = sys.argv[1:]
    mcp = McpClient(); mcp.initialize(); tools = to_ollama_tools(mcp.list_tools())
    log = open(os.path.join(HERE, "agent_local.log"), "a")
    print(f"tools offered: {[t['function']['name'] for t in tools]}", file=log, flush=True)
    for ex in examples:
        n = ex["name"]
        if only and n not in only:
            continue
        base = os.path.join(OUT, n)
        if os.path.exists(os.path.join(base, "result.json")):
            continue
        os.makedirs(base, exist_ok=True)
        trace = open(os.path.join(base, "trace.jsonl"), "w")
        hook(ex.get("pre"), log)
        infra = infra_start(ex.get("infra", [])) if ex.get("infra") else {}
        if infra:
            trace.write(json.dumps({"infra": infra}) + "\n"); trace.flush()
        seeded = seed_files(n, os.path.join(base, "seed-check")) if ex.get("seed") else []
        shutil.rmtree(os.path.join(base, "seed-check"), ignore_errors=True)
        prompt = f"Create a runnable Camel CLI example: {ex['prompt']}."
        if ex.get("hint"):
            prompt += " " + ex["hint"]
        if seeded:
            prompt += ("\n\nThe project folder already contains these files; use them and do not rewrite them: "
                       + ", ".join(seeded) + ".")
            # ladder (09-19): a developer opens the data file before writing the route; the model has no file tool,
            # so the prompt shows the content of the small text seeds (one file per directory, the rest have the same
            # shape). Dry run 3 guessed $.lineItems and $.items for a field called lines.
            prompt += seed_contents(n, seeded)
        prompt += infra_prompt(infra)
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt}]
        result = {"name": n, "rounds": 0, "tool_calls": 0, "ok": False, "seconds": 0, "tokens": 0}
        t_start = time.time()
        last_call, last_out = None, ""
        for rnd in range(1, MAX_ROUNDS + 1):
            result["rounds"] = rnd
            calls = 0
            text = ""
            while True:
                try:
                    data, secs = ollama_chat(messages, tools)
                except Exception as e:
                    text = ""; trace.write(json.dumps({"round": rnd, "error": str(e)}) + "\n"); break
                msg = data["message"]; result["tokens"] += data.get("eval_count", 0)
                trace.write(json.dumps({"round": rnd, "secs": round(secs, 1), "eval": data.get("eval_count"),
                                        "prompt_eval": data.get("prompt_eval_count"),
                                        "tool_calls": msg.get("tool_calls"), "content": (msg.get("content") or "")[:400]}) + "\n")
                trace.flush()
                messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg.get("tool_calls")})
                if msg.get("tool_calls") and calls >= MAX_TOOL_CALLS and not text:
                    # round 2 harness fix: the model wants another tool call but the round's budget is spent; before,
                    # the empty content of that message was taken as the answer and the round failed on "the file has
                    # no YAML" (seen on openapi-server). Tell it the budget is spent and let it answer without tools.
                    messages.append({"role": "user", "content":
                                     f"You have used the {MAX_TOOL_CALLS} tool calls allowed in this round. Answer now with the "
                                     "complete files in the '=== FILE: <name> ===' format, without further tool calls."})
                    try:
                        data, secs = ollama_chat(messages, [])
                    except Exception as e:
                        trace.write(json.dumps({"round": rnd, "error": str(e)}) + "\n"); break
                    msg = data["message"]; result["tokens"] += data.get("eval_count", 0)
                    trace.write(json.dumps({"round": rnd, "secs": round(secs, 1), "eval": data.get("eval_count"),
                                            "budget_spent": True, "content": (msg.get("content") or "")[:400]}) + "\n")
                    trace.flush()
                    messages.append({"role": "assistant", "content": msg.get("content") or ""})
                    text = msg.get("content") or ""
                    break
                if msg.get("tool_calls") and calls < MAX_TOOL_CALLS:
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]; calls += 1; result["tool_calls"] += 1
                        args = fn.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        # ladder (09-19): the same call as the previous one (name and arguments) is answered from
                        # the previous result with a note, so a model that repeats a validation of unchanged content
                        # (error-handling repeated one ten times in the dry run) is told instead of charged a round trip
                        key = (fn["name"], json.dumps(args, sort_keys=True))
                        if key == last_call:
                            out = ("This is the same call as your previous one, with the same arguments, so the answer is "
                                   "unchanged. Change the content before validating again.\n\n" + last_out)
                        else:
                            try:
                                out = mcp.call(fn["name"], args)
                            except Exception as e:
                                out = "ERROR: " + str(e)
                            last_call, last_out = key, out
                        out = out[:TOOL_RESULT_CAP]
                        trace.write(json.dumps({"round": rnd, "tool": fn["name"], "args": args, "result": out[:600]}) + "\n")
                        trace.flush()
                        messages.append({"role": "tool", "content": out, "tool_name": fn["name"]})
                    continue
                text = msg.get("content") or ""
                break
            if not text.strip():
                # an empty answer (a spiral that ran out, a tool budget hit): say so, nothing to save or run
                print(f"{n}: round{rnd} calls={calls} empty answer", file=log, flush=True)
                messages.append({"role": "user", "content": "Your answer was empty: it contained no files. Output the complete files in the '=== FILE: <name> ===' format."})
                continue
            folder = os.path.join(base, f"attempt{rnd}")
            os.makedirs(folder, exist_ok=True)
            if ex.get("seed"):
                seed_files(n, folder)
            files = write_files(text, folder)
            with open(os.path.join(folder, "raw.txt"), "w") as f:
                f.write(text)
            # after the series (09-19): the given files stay given. The model rewrote the seeded stylesheet in all
            # three xslt attempts of every suite (with a wrong XSL namespace) although the prompt says not to; the
            # seeds are restored after the model's files are written and the feedback says which were restored
            restored = []
            if ex.get("seed"):
                src = os.path.join(HERE, "seed", n)
                for rel in ex.get("seed_files", []):
                    dst = os.path.join(folder, rel)
                    if os.path.basename(rel) in files:
                        shutil.copy2(os.path.join(src, rel), dst)
                        restored.append(rel)
                if restored:
                    print(f"{n}: round{rnd} restored seed files rewritten by the model: {restored}", file=log, flush=True)
            ok, v, errs, nroutes, activity = run_folder(folder, ex["run_seconds"], ex.get("probe"), ex.get("probe_regex"), ex)
            print(f"{n}: round{rnd} calls={calls} files={files} ok={ok} routes={nroutes} activity={activity}", file=log, flush=True)
            if ok:
                result["ok"] = True
                break
            fb = "I saved and ran your files with the Camel CLI.\n\n`camel validate yaml` output:\n" + (v.strip() or "(passed)")
            if restored:
                fb = ("You rewrote " + ", ".join(restored) + ", which the project already provides; the original was kept "
                      "and your version discarded. Use the given file as it is.\n\n" + fb)
            if errs:
                fb += "\n\nErrors from `camel run`:\n" + errs
            if nroutes == 0 and not errs:
                fb += "\n\nThe application started but loaded 0 routes."
            if nroutes > 0 and not activity and "Failed" not in errs and "Exception" not in errs:
                fb += (f"\n\nThe route loaded but produced no log output in {ex['run_seconds']} seconds: no message went "
                       "through any route. It must produce output on its own (a timer trigger, or a file consumer on a "
                       "directory that contains the input files named in the request).")
            fb += "\n\nUse the tools to check the options you are unsure about and validate the YAML, then output the complete corrected files again in the same '=== FILE: <name> ===' format."
            messages.append({"role": "user", "content": fb})
        result["seconds"] = round(time.time() - t_start, 1)
        json.dump(result, open(os.path.join(base, "result.json"), "w"))
        json.dump(messages, open(os.path.join(base, "messages.json"), "w"))
        trace.close()
        if ex.get("infra"):
            infra_stop(ex["infra"])
        hook(ex.get("post"), log)
        print(f"{n}: DONE ok={result['ok']} rounds={result['rounds']} tool_calls={result['tool_calls']} secs={result['seconds']} tokens={result['tokens']}", file=log, flush=True)
    log.close()


if __name__ == "__main__":
    main()
