#!/usr/bin/env python3
"""Markdown summary of completed runs: one-shot and stepwise results plus the suite wall clock.

Usage: summarize_runs.py <tag> [<tag> ...]

A run with tag T has its one-shot results in oneshot-T/<example>/result.json (BENCH_OUT=oneshot-T), its stepwise
results in stepwise/T/results.json (BENCH_TAG=T) and its wall clock in T.log (written by run-suite.sh).
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
names = [e["name"] for e in json.load(open(os.path.join(HERE, "examples.json")))]
tags = sys.argv[1:]
if not tags:
    print(__doc__); sys.exit(1)
def wall(tag):
    p = os.path.join(HERE, tag + ".log")
    if not os.path.exists(p):
        return None
    t = {}
    for l in open(p):
        m = re.search(rf"\[{re.escape(tag)}\] (one-shot|stepwise) (start|done) (\d+):(\d+):(\d+)", l)
        if m:
            t[(m.group(1), m.group(2))] = int(m.group(3)) * 3600 + int(m.group(4)) * 60 + int(m.group(5))
    try:
        def span(x):
            d = t[(x, "done")] - t[(x, "start")]
            return d + 86400 if d < 0 else d  # a run that crosses midnight
        return span("one-shot"), span("stepwise")
    except KeyError:
        return None
STALL = 600  # a single model call longer than this is the machine asleep, not the model
def stalls(paths):
    total = 0.0
    for p in paths:
        if not os.path.exists(p):
            continue
        for l in open(p):
            try:
                o = json.loads(l)
            except json.JSONDecodeError:
                continue
            if isinstance(o.get("secs"), (int, float)) and o["secs"] > STALL:
                total += o["secs"]
    return total
rows = {}
for tag in tags:
    d = os.path.join(HERE, "oneshot-" + tag)
    one = [json.load(open(os.path.join(d, n, "result.json"))) for n in names if os.path.exists(os.path.join(d, n, "result.json"))]
    sp = os.path.join(HERE, "stepwise", tag, "results.json")
    st = json.load(open(sp)) if os.path.exists(sp) else []
    w = wall(tag)
    st1 = stalls(os.path.join(d, n, "trace.jsonl") for n in names)
    st2 = stalls(os.path.join(HERE, "stepwise", tag, f"step{i}.trace.jsonl") for i in range(1, len(st) + 1))
    if w and (st1 or st2):
        w = (int(w[0] - st1), int(w[1] - st2))
    rows[tag] = dict(
        n=len(one), stall=int(st1 + st2),
        ok=sum(x["ok"] for x in one), first=sum(1 for x in one if x["ok"] and x["rounds"] == 1),
        rounds=sum(x["rounds"] for x in one), calls=sum(x["tool_calls"] for x in one),
        tok=sum(x["tokens"] for x in one),
        sn=len(st), sok=sum(x["ok"] for x in st),
        slen=sum(1 for x in st if x["ok"] or (x["file_ok"] and x["props_ok"] and x["errors"] == 0)),
        scalls=sum(x["tool_calls"] for x in st), srefused=sum(x["refused_writes"] for x in st), stok=sum(x["tokens"] for x in st),
        wall=(f"{(w[0]+w[1])//60} min ({w[0]//60} + {w[1]//60})" if w else "?"),
        fails=[n for n, x in zip(names, one) if not x["ok"]], sfails=[i + 1 for i, x in enumerate(st) if not x["ok"]])
def line(label, f):
    return "| " + label + " | " + " | ".join(f(rows[t]) for t in tags) + " |"
print("| | " + " | ".join(tags) + " |"); print("|---|" + "---|" * len(tags))
print(line("One-shot passes", lambda x: f"{x['ok']} of {x['n']}"))
print(line("One-shot first-round passes", lambda x: str(x["first"])))
print(line("One-shot rounds / tool calls", lambda x: f"{x['rounds']} / {x['calls']}"))
print(line("One-shot tokens", lambda x: f"{x['tok']:,}"))
print(line("Stepwise passes (strict / lenient)", lambda x: f"{x['sok']} / {x['slen']} of {x['sn']}"))
print(line("Stepwise tool calls / refused writes", lambda x: f"{x['scalls']} / {x['srefused']}"))
print(line("Stepwise tokens", lambda x: f"{x['stok']:,}"))
print(line("Suite wall clock (sleep stalls removed)", lambda x: x["wall"] + (f", {x['stall']//60} min asleep" if x["stall"] else "")))
print(line("One-shot failures", lambda x: ", ".join(x["fails"]) or "none"))
print(line("Stepwise failures", lambda x: ", ".join(map(str, x["sfails"])) or "none"))
