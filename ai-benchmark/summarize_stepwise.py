#!/usr/bin/env python3
"""Per example and step, the passes over the runs of a stepwise ladder series: summarize_stepwise.py <tag> [k]"""
import json, os, sys
tag = sys.argv[1]; k = int(sys.argv[2]) if len(sys.argv) > 2 else 1
tags = [f"{tag}-{i}" for i in range(1, k + 1)] if k > 1 else [tag]
names = sorted(os.path.splitext(f)[0] for f in os.listdir("steps-ladder") if f.endswith(".json"))
print(f"| example | steps | passes per step ({' '.join(tags)}) | all steps passed |")
print("|---|---|---|---|")
total = 0; possible = 0; clean = 0
for n in names:
    per = []; runs = []
    for t in tags:
        p = os.path.join("stepwise", t, n, "results.json")
        if not os.path.exists(p):
            continue
        res = json.load(open(p)); runs.append(res)
    if not runs:
        continue
    steps = max(len(r) for r in runs)
    cols = []
    for s in range(steps):
        ok = sum(1 for r in runs if s < len(r) and r[s]["ok"]); cols.append(f"{ok}/{len(runs)}"); total += ok; possible += len(runs)
    allok = sum(1 for r in runs if r and all(x["ok"] for x in r)); clean += allok
    print(f"| {n} | {steps} | {' '.join(cols)} | {allok}/{len(runs)} |")
print(f"\nsteps passed: {total} of {possible}; runs with every step passed: {clean}")
