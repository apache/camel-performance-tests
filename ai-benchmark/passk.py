#!/usr/bin/env python3
"""Consistency over k runs of the same examples: per-example passes out of k, pass@k and pass^k.

Usage: passk.py <tag-1> <tag-2> ... (the tags of k runs made with run-suite.sh <tag> <k>)

pass@k = share of examples that passed in at least one of the k runs (what a user gets with k tries).
pass^k = share of examples that passed in every run (what a user gets every time).
Both follow the definitions in the MuleSoft integration-skill benchmark post (2026-08) so the two can be compared.
The examples file is BENCH_EXAMPLES (default examples.json), as for the run itself.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
names = [e["name"] for e in json.load(open(os.path.join(HERE, os.environ.get("BENCH_EXAMPLES", "examples.json"))))]
tags = sys.argv[1:]
if len(tags) < 2:
    print(__doc__); sys.exit(1)
res = {}
for t in tags:
    for n in names:
        p = os.path.join(HERE, "oneshot-" + t, n, "result.json")
        res[(t, n)] = json.load(open(p)) if os.path.exists(p) else None
k = len(tags)
print("| example | passes of %d | first-round passes | rounds | tokens |" % k)
print("|---|---|---|---|---|")
any_pass = all_pass = 0
for n in names:
    rs = [res[(t, n)] for t in tags if res[(t, n)]]
    ok = sum(1 for r in rs if r["ok"])
    first = sum(1 for r in rs if r["ok"] and r["rounds"] == 1)
    any_pass += ok > 0
    all_pass += 1 if rs and ok == len(tags) else 0
    print(f"| {n} | {ok} | {first} | {', '.join(str(r['rounds']) for r in rs)} | {', '.join(f'{r['tokens']:,}' for r in rs)} |")
n = len(names)
print()
print(f"pass@{k}: {any_pass} of {n} ({100 * any_pass / n:.0f}%)")
print(f"pass^{k}: {all_pass} of {n} ({100 * all_pass / n:.0f}%)")
per_run = [sum(1 for m in names if res[(t, m)] and res[(t, m)]["ok"]) for t in tags]
print(f"passes per run: {', '.join(map(str, per_run))} (mean {sum(per_run) / k:.1f} of {n})")
