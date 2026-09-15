#!/usr/bin/env python3
"""Stepwise editing benchmark against camel-jbang-mcp (camel mcp --http), using the shared authoring tools
from CAMEL-24695.

The model gets the shared authoring set (camel_catalog_doc, camel_catalog_find, camel_validate_source,
camel_get_files, camel_write_file, camel_run, camel_control, camel_get_log, camel_get_errors,
camel_eval_expression, camel_error_diagnose) plus the structured catalog tools, and a short neutral system
prompt. The harness starts the integration once with camel_run (dev mode) before step 1, then sends the
8 requests one at a time. Scoring: files on disk, log via camel_get_log,
errors via camel_get_errors, diff size, reference checkpoint after each step.

Env: BENCH_MODEL (ollama model), MCP_URL (default http://127.0.0.1:9090/mcp), BENCH_TAG (results folder name),
BENCH_STEPS (the steps file, default steps.json),
BENCH_TOOL_CALLS (max tool calls per step, default 12).
"""
import difflib, json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient  # noqa: E402

MODEL = os.environ.get("BENCH_MODEL", "qwen3.6:35b-a3b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:9090/mcp")
HERE = os.path.dirname(os.path.abspath(__file__))
TAG = os.environ.get("BENCH_TAG", "mcp-" + MODEL.replace(":", "_").replace("/", "_"))
OUT = os.path.join(HERE, "stepwise", TAG)
MAX_TOOL_CALLS = int(os.environ.get("BENCH_TOOL_CALLS", "12"))
TOOL_RESULT_CAP = 6000

SHARED = ["camel_catalog_doc", "camel_catalog_find", "camel_catalog_sample", "camel_validate_source", "camel_get_files", "camel_write_file",
          "camel_run", "camel_control", "camel_get_log", "camel_get_errors", "camel_eval_expression", "camel_error_diagnose"]
EXTRA = ["camel_catalog_components", "camel_catalog_component_doc", "camel_catalog_eips", "camel_catalog_eip_doc",
         "camel_catalog_languages", "camel_catalog_language_doc", "camel_catalog_dataformats", "camel_catalog_dataformat_doc"]

SYSTEM = (
    "You are an Apache Camel assistant helping a developer edit a running Camel integration through the Camel MCP server.\n\n"
    "The project directory is {directory}. The integration {name} is already running from it in dev mode: files you write are "
    "reloaded automatically.\n\n"
    "Guidelines:\n"
    "- To edit: camel_get_files (directory, optionally file) to read, then camel_write_file (directory, file, content) with the "
    "complete file. Invalid YAML or properties is refused with errors: fix them (camel_catalog_doc has the option names) and write again.\n"
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
    body = json.dumps({"model": MODEL, "messages": messages, "tools": tools, "stream": False,
                       "options": {"temperature": 0.2, "num_ctx": 32768}}).encode()
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


def score(step, project, cfg, mcp, name, before):
    chk = step["check"]
    route = read(os.path.join(project, cfg["route_file"])); props = read(os.path.join(project, cfg["props_file"]))
    result = {"file_ok": True, "props_ok": True, "log_ok": True, "errors": 0}
    if chk.get("file_regex") and not re.search(chk["file_regex"], route):
        result["file_ok"] = False
    if chk.get("file_regex2") and not re.search(chk["file_regex2"], route):
        result["file_ok"] = False
    if chk.get("file_not_regex") and re.search(chk["file_not_regex"], route):
        result["file_ok"] = False
    if chk.get("props_regex") and not re.search(chk["props_regex"], props):
        result["props_ok"] = False
    time.sleep(cfg["wait_seconds"])
    lines = log_lines(mcp, name, 40)
    def lvl(l): return (l.get("level") or "").upper()
    def msg(l): return l.get("message") or l.get("msg") or ""
    recent = [l for l in lines if isinstance(l, dict) and lvl(l) == "INFO"]
    msgs = [msg(l) for l in recent]
    matched = [m for m in msgs if re.search(chk["log_regex"], m)]
    if len(matched) < chk.get("min_log", 1):
        result["log_ok"] = False
    if chk.get("interval_min") and len(matched) >= 2:
        ts = [l.get("time") or l.get("timestamp") or "" for l in recent if re.search(chk["log_regex"], msg(l))][:2]
        try:
            def sec(t):
                t = t.split("T")[-1].split(" ")[-1]; h, m, s = t.split(":")[:3]; return int(h) * 3600 + int(m) * 60 + float(s)
            if abs(sec(ts[0]) - sec(ts[1])) < chk["interval_min"]:
                result["log_ok"] = False
        except Exception:
            pass
    result["errors"] = sum(1 for l in lines if isinstance(l, dict) and lvl(l) == "ERROR")
    data, _ = jcall(mcp, "camel_get_errors", {"name": name})
    if isinstance(data, dict):
        result["errors"] += len(data.get("errors", []) or [])
    diff = list(difflib.unified_diff(before["route"].splitlines(), route.splitlines(), lineterm="", n=0))
    diffp = list(difflib.unified_diff(before["props"].splitlines(), props.splitlines(), lineterm="", n=0))
    result["changed_lines"] = sum(1 for l in diff + diffp if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---")))
    result["ok"] = result["file_ok"] and result["props_ok"] and result["log_ok"] and result["errors"] == 0
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

    # start the integration once, in dev mode, through the MCP server
    data, raw = jcall(mcp, "camel_run", {"directory": project})
    print(f"camel_run -> {raw[:300]}", file=log, flush=True)
    name = (data or {}).get("name") or os.path.basename(project)
    time.sleep(6)

    messages = [{"role": "system", "content": SYSTEM.replace("{directory}", project).replace("{name}", name)}]
    results = []
    try:
        for step in cfg["steps"]:
            sid = step["id"]
            before = {"route": read(os.path.join(project, cfg["route_file"])), "props": read(os.path.join(project, cfg["props_file"]))}
            trace = open(os.path.join(OUT, f"step{sid}.trace.jsonl"), "w")
            messages.append({"role": "user", "content": step["request"]})
            calls = 0; tokens = 0; t0 = time.time(); writes = 0; refused = 0; answer = ""
            while True:
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
                        if fn["name"] in ("camel_get_files", "camel_write_file", "camel_validate_source", "camel_run") and "directory" not in args:
                            args["directory"] = project
                        if fn["name"] in ("camel_get_log", "camel_get_errors", "camel_control", "camel_eval_expression") and "name" not in args:
                            args["name"] = name
                        if fn["name"] == "camel_write_file":
                            writes += 1
                        try:
                            out = mcp.call(fn["name"], args)
                        except Exception as e:
                            out = "ERROR: " + str(e)
                        if fn["name"] == "camel_write_file" and ('"invalid"' in out or out.startswith("ERROR")):
                            refused += 1
                        out = out[:TOOL_RESULT_CAP]
                        trace.write(json.dumps({"tool": fn["name"], "args": {k: (v if k != "content" else v[:1500]) for k, v in args.items()}, "result": out[:800]}) + "\n"); trace.flush()
                        messages.append({"role": "tool", "content": out, "tool_name": fn["name"]})
                    continue
                answer = msg.get("content") or ""
                break
            res, route_after, props_after = score(step, project, cfg, mcp, name, before)
            res.update({"step": sid, "request": step["request"], "tool_calls": calls, "writes": writes, "refused_writes": refused,
                        "seconds": round(time.time() - t0, 1), "tokens": tokens, "answer": answer[:400]})
            results.append(res)
            with open(os.path.join(OUT, f"step{sid}.after.yaml"), "w") as f:
                f.write(route_after)
            print(f"step{sid}: ok={res['ok']} file={res['file_ok']} props={res['props_ok']} log={res['log_ok']} errors={res['errors']} "
                  f"changed_lines={res['changed_lines']} calls={calls} writes={writes} refused={refused} secs={res['seconds']} tokens={tokens}", file=log, flush=True)
            trace.close()
            if step.get("reference"):
                for fname, content in step["reference"].items():
                    with open(os.path.join(project, fname), "w") as f:
                        f.write(content)
                time.sleep(4)
                if not res["ok"]:
                    messages.append({"role": "user", "content": "I fixed that step myself; the files now contain the correct version. Continue with the next request."})
            json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    finally:
        data, raw = jcall(mcp, "camel_control", {"name": name, "action": "stop"})
        print(f"camel_control stop -> {raw[:200]}", file=log, flush=True)
    print(f"DONE passed={sum(1 for r in results if r['ok'])}/{len(results)}", file=log, flush=True)
    log.close()


if __name__ == "__main__":
    main()
