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
import json, os, re, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient  # noqa: E402
from gen_local import write_files, strip_think  # noqa: E402

MODEL = os.environ.get("BENCH_MODEL", "qwen3.6:35b-a3b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.environ.get("BENCH_OUT", "oneshot"))
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
    body = json.dumps({"model": MODEL, "messages": messages, "tools": tools, "stream": False,
                       "options": {"temperature": 0.2, "num_ctx": 32768}}).encode()
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


def run_folder(folder, secs, probe):
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
    activity = len(re.findall(r"\.yaml:\d+ |\.java:\d+ ", r)) > 0 or bool(p.strip())
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
    ok = (not bad_validate) and nroutes > 0 and not errs and activity
    return ok, v, "\n".join(errs[:15]), nroutes, activity


def main():
    examples = json.load(open(os.path.join(HERE, "examples.json")))
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
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Create a runnable Camel CLI example: {ex['prompt']}."}]
        result = {"name": n, "rounds": 0, "tool_calls": 0, "ok": False, "seconds": 0, "tokens": 0}
        t_start = time.time()
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
                if msg.get("tool_calls") and calls < MAX_TOOL_CALLS:
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]; calls += 1; result["tool_calls"] += 1
                        args = fn.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        try:
                            out = mcp.call(fn["name"], args)
                        except Exception as e:
                            out = "ERROR: " + str(e)
                        out = out[:TOOL_RESULT_CAP]
                        trace.write(json.dumps({"round": rnd, "tool": fn["name"], "args": args, "result": out[:600]}) + "\n")
                        trace.flush()
                        messages.append({"role": "tool", "content": out, "tool_name": fn["name"]})
                    continue
                text = msg.get("content") or ""
                break
            folder = os.path.join(base, f"attempt{rnd}")
            files = write_files(text, folder)
            with open(os.path.join(folder, "raw.txt"), "w") as f:
                f.write(text)
            ok, v, errs, nroutes, activity = run_folder(folder, ex["run_seconds"], ex.get("probe"))
            print(f"{n}: round{rnd} calls={calls} files={files} ok={ok} routes={nroutes} activity={activity}", file=log, flush=True)
            if ok:
                result["ok"] = True
                break
            fb = "I saved and ran your files with the Camel CLI.\n\n`camel validate yaml` output:\n" + (v.strip() or "(passed)")
            if errs:
                fb += "\n\nErrors from `camel run`:\n" + errs
            if nroutes == 0 and not errs:
                fb += "\n\nThe application started but loaded 0 routes."
            if nroutes > 0 and not errs and not activity:
                fb += (f"\n\nThe route loaded but produced no log output in {ex['run_seconds']} seconds; it must produce "
                       "output on its own (timer trigger, or create the input files it reads).")
            fb += "\n\nUse the tools to check the options you are unsure about and validate the YAML, then output the complete corrected files again in the same '=== FILE: <name> ===' format."
            messages.append({"role": "user", "content": fb})
        result["seconds"] = round(time.time() - t_start, 1)
        json.dump(result, open(os.path.join(base, "result.json"), "w"))
        json.dump(messages, open(os.path.join(base, "messages.json"), "w"))
        trace.close()
        print(f"{n}: DONE ok={result['ok']} rounds={result['rounds']} tool_calls={result['tool_calls']} secs={result['seconds']} tokens={result['tokens']}", file=log, flush=True)
    log.close()


if __name__ == "__main__":
    main()
