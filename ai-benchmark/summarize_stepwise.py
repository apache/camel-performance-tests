#!/usr/bin/env python3
"""Per example and step, the passes over the runs of a stepwise ladder series: summarize_stepwise.py <tag> [k]

A step passes (ok) when its files, log and probes are right and it logged no new errors; final state right (ok_final)
leaves the errors out: a model that tests its own app (the HTTP request tool) causes errors on the way to a right
answer, which ok counts against it. Last version right (ok_lastwrite) is in between: the final state is right and no
errors were logged after the model's last accepted write; runs before it was recorded count it as ok."""
import json, os, sys
tag = sys.argv[1]; k = int(sys.argv[2]) if len(sys.argv) > 2 else 1
tags = [f"{tag}-{i}" for i in range(1, k + 1)] if k > 1 else [tag]
names = sorted(os.path.splitext(f)[0] for f in os.listdir("steps-ladder") if f.endswith(".json"))
print(f"| example | steps | passes per step ({' '.join(tags)}) | all steps passed | last version right | final state right |")
print("|---|---|---|---|---|---|")
total = 0; possible = 0; clean = 0; final = 0; lastw = 0
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
    fin = sum(1 for r in runs for x in r if x.get("ok_final", x["ok"])); final += fin
    lw = sum(1 for r in runs for x in r if x.get("ok_lastwrite", x["ok"])); lastw += lw
    n_steps = sum(len(r) for r in runs)
    print(f"| {n} | {steps} | {' '.join(cols)} | {allok}/{len(runs)} | {lw}/{n_steps} | {fin}/{n_steps} |")
print(f"\nsteps passed: {total} of {possible}; last version right: {lastw} of {possible}; final state right: {final} of"
      f" {possible}; runs with every step passed: {clean}")
