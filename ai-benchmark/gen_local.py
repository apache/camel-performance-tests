#!/usr/bin/env python3
"""Generate Camel examples from one-line prompts with a local Ollama model.

Condition B1: bare prompt, no tools.  Writes files under local/<name>/attempt1/.
Condition B2 is applied later by bench_run.py: if attempt1 fails validation, the
validator output is fed back once and the result goes to local/<name>/attempt2/.
"""
import json, os, re, sys, time, urllib.request

MODEL = os.environ.get("BENCH_MODEL", "qwen3.6:35b-a3b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "local")

SYSTEM = """You are an Apache Camel 4.23 expert. The user wants a small runnable example for the Camel CLI (camel-jbang).
Write it in Camel YAML DSL. Use the file extension .camel.yaml for routes. If the example needs extra files
(application.properties, a Java bean, an XSLT stylesheet, an input file), include them too.
Do not use Maven, Spring Boot or Quarkus. Do not explain. Output only files, each in this exact format:

=== FILE: <filename> ===
<file content>

Output nothing before the first '=== FILE:' line and nothing after the last file."""


def chat(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False,
                       "options": {"temperature": 0.2, "num_ctx": 16384}}).encode()
    req = urllib.request.Request(HOST + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.load(r)
    return data["message"]["content"], time.time() - t0, data


def strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def write_files(text, folder):
    os.makedirs(folder, exist_ok=True)
    text = strip_think(text)
    parts = re.split(r"^=== FILE: (.+?) ===\s*$", text, flags=re.M)
    # run 11 on: a file block written inside a ``` fence ends at the closing fence, so an explanation the model
    # appends after the last fence no longer lands in that file (runs 1-10 folded it into the file, and the
    # validator then named it, which cost a round or the example)
    fenced = os.environ.get("BENCH_FENCE_AWARE", "1") == "1"
    def unfence(content):
        lines = content.strip("\n").split("\n")
        if fenced and lines and lines[0].strip().startswith("```"):
            body = []
            for l in lines[1:]:
                if l.strip().startswith("```"):
                    break
                body.append(l)
            return "\n".join(body)
        return "\n".join(l for l in lines if not l.strip().startswith("```"))
    parts = [parts[0]] + [unfence(p) if i % 2 == 0 else p for i, p in enumerate(parts[1:], 1)]
    written = []
    if len(parts) < 3:
        # model ignored the format; dump as a single yaml file
        with open(os.path.join(folder, "route.camel.yaml"), "w") as f:
            f.write(text.strip() + "\n")
        return ["route.camel.yaml (fallback)"]
    for i in range(1, len(parts), 2):
        name = os.path.basename(parts[i].strip())
        content = parts[i + 1].strip("\n") + "\n"
        with open(os.path.join(folder, name), "w") as f:
            f.write(content)
        written.append(name)
    return written


def main():
    examples = json.load(open(os.path.join(HERE, "examples.json")))
    only = sys.argv[1:]
    log = open(os.path.join(HERE, "gen_local.log"), "a")
    for ex in examples:
        if only and ex["name"] not in only:
            continue
        folder = os.path.join(OUT, ex["name"], "attempt1")
        if os.path.exists(os.path.join(folder, "raw.txt")):
            continue
        user = f"Create a runnable Camel CLI example: {ex['prompt']}."
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        try:
            text, secs, data = chat(msgs)
        except Exception as e:
            print(f"{ex['name']}: ERROR {e}", file=log, flush=True)
            continue
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "raw.txt"), "w") as f:
            f.write(text)
        with open(os.path.join(folder, "messages.json"), "w") as f:
            json.dump(msgs, f)
        files = write_files(text, folder)
        ev = data.get("eval_count", 0); pe = data.get("prompt_eval_count", 0)
        print(f"{ex['name']}: {secs:.1f}s prompt={pe} gen={ev} files={files}", file=log, flush=True)
    log.close()


if __name__ == "__main__":
    main()
