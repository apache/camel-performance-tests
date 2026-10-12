#!/usr/bin/env python3
"""Per-language metrics of the FeatureRoutes load runs (unbounded 60-300 s, fixed 100 msg/s 60-180 s)."""
import csv
import json
import os
import re
import sys

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw", "load")
LANGS = ["java", "groovy", "js", "quickjs", "quickjs-pr209", "quickjs-pr209native", "quickjs-pr209native-jdk25", "quickjs-stateless", "jactl", "mvel", "python3", "python"]
# result file suffixes of the quickjs4j PR 209 runs (same features-quickjs variant, -Djmh.suffix)
FILES = {"quickjs-pr209": ("features-quickjs", "-pr209"), "quickjs-pr209native": ("features-quickjs", "-pr209native"), "quickjs-pr209native-jdk25": ("features-quickjs", "-pr209native-jdk25"), "quickjs-stateless": ("features-quickjs", "-pr209-stateless")}
PAUSE = re.compile(r"\[(?P<up>\d+\.\d+)s\].*GC\(\d+\) Pause (?P<kind>Young|Full|Remark|Cleanup)(?: \((?P<qual>[^)]*)\))?(?: \((?P<qual2>[^)]*)\))? (?P<before>\d+)M->(?P<after>\d+)M\(\d+M\) (?P<ms>\d+\.\d+)ms")


def csv_summary(path, warmup, until):
    if not os.path.exists(path):
        return None
    msgs, p50, p99, p999, bytes_, cpu, meta, heap, classes = [], [], [], [], [], [], [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            s = float(r["seconds"])
            if s > warmup and s <= until:
                msgs.append(float(r["msgPerSec"]))
                p50.append(float(r["p50us"]))
                p99.append(float(r["p99us"]))
                p999.append(float(r["p999us"]))
                bytes_.append(float(r["allocBytesPerMsg"]))
                cpu.append(float(r["processCpuLoad"]))
                meta.append(float(r["metaspaceMB"]))
                heap.append(float(r["heapUsedMB"]))
                classes.append(float(r["classesLoadedTotal"]))
    if not msgs:
        return None
    med = lambda xs: sorted(xs)[len(xs) // 2]
    return {"msg": sum(msgs) / len(msgs), "p50": med(p50), "p99": med(p99), "p999": med(p999),
            "bytes": sum(bytes_) / len(bytes_), "cpu": 100 * sum(cpu) / len(cpu),
            "metaspace": meta[-1], "heapUsedMax": max(heap), "classesLoaded": classes[-1] - classes[0]}


def gc_summary(path, warmup, until):
    if not os.path.exists(path):
        return None
    counts, total, mx, after_young = {}, {}, 0.0, []
    with open(path) as f:
        for line in f:
            m = PAUSE.search(line)
            if not m:
                continue
            up = float(m.group("up"))
            if up <= warmup or up > until:
                continue
            qual = (m.group("qual") or "") + (m.group("qual2") or "")
            k = m.group("kind").lower()
            if k == "young" and "Mixed" in qual:
                k = "mixed"
            ms = float(m.group("ms"))
            counts[k] = counts.get(k, 0) + 1
            total[k] = total.get(k, 0.0) + ms
            mx = max(mx, ms)
            if k == "young":
                after_young.append(int(m.group("after")))
    if not counts:
        # log present but no pause inside the window (fixed-rate runs allocate too little to trigger a collection)
        return {"pauses": 0, "pausePct": 0.0, "maxPauseMs": 0.0, "full": 0, "mixed": 0, "remark": 0,
                "heapAfterGcFirst": None, "heapAfterGcLast": None}
    window = until - warmup
    n = len(after_young)
    third = max(1, n // 3)
    return {"pauses": sum(counts.values()), "pausePct": sum(total.values()) / (window * 1000) * 100, "maxPauseMs": mx,
            "full": counts.get("full", 0), "mixed": counts.get("mixed", 0), "remark": counts.get("remark", 0),
            "heapAfterGcFirst": sum(after_young[:third]) / third if n else None,
            "heapAfterGcLast": sum(after_young[-third:]) / third if n else None}


def main():
    out = {}
    for lang in LANGS:
        v, sfx = FILES.get(lang, (f"features-{lang}", ""))
        out[lang] = {
            "unbounded": {"harness": csv_summary(f"{RAW}/GroovyLoadTest-{v}{sfx}.csv", 60, 300),
                          "gc": gc_summary(f"{RAW}/{v}{sfx}-gc.log", 60, 300)},
            "rate100": {"harness": csv_summary(f"{RAW}/GroovyLoadTest-{v}-rate100{sfx}.csv", 60, 180),
                        "gc": gc_summary(f"{RAW}/{v}-rate100{sfx}-gc.log", 60, 180)},
        }
    dest = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdout"
    with open(dest, "w") as f:
        json.dump(out, f, indent=1)
    for lang in LANGS:
        for mode in ("unbounded", "rate100"):
            h = out[lang][mode]["harness"]
            g = out[lang][mode]["gc"]
            if h:
                print(f"{lang:8s} {mode:9s} {h['msg']:>12,.0f} msg/s  p50 {h['p50']:>8,.0f}  p99 {h['p99']:>9,.0f} us  "
                      f"{h['bytes']:>9,.0f} B/msg  cpu {h['cpu']:5.1f}%  meta {h['metaspace']:5.1f} MB  "
                      + (f"gc {g['pausePct']:.2f}% max {g['maxPauseMs']:.0f} ms heapAfterGC {g['heapAfterGcFirst'] or 0:.0f}->{g['heapAfterGcLast'] or 0:.0f} MB full {g['full']}" if g else "no gc log"))


if __name__ == "__main__":
    main()
