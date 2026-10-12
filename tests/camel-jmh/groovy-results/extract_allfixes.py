#!/usr/bin/env python3
"""Build the before/after data block for the chart page from the all-fixes JMH JSON and load CSVs."""
import csv
import glob
import json
import os
import sys

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")


def rows(path):
    out = {}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return out
    for b in json.load(open(path)):
        name = b["benchmark"].rsplit(".", 1)[-1]
        params = ",".join(f"{k}={v}" for k, v in sorted(b.get("params", {}).items()))
        pm = b["primaryMetric"]
        gc = None
        for k, v in b.get("secondaryMetrics", {}).items():
            if k.endswith("gc.alloc.rate.norm"):
                gc = v["score"]
        key = (name, params, b["mode"])
        p99 = pm.get("scorePercentiles", {}).get("99.0")
        out[key] = {"score": pm["score"], "err": pm["scoreError"], "unit": pm["scoreUnit"], "gc": gc, "p99": p99}
    return out


def compare(before, after):
    res = []
    for key, a in after.items():
        b = before.get(key)
        if not b:
            continue
        name, params, mode = key
        if mode == "thrpt":
            ratio = a["score"] / b["score"] if b["score"] else None
        else:
            ratio = b["score"] / a["score"] if a["score"] else None
        res.append({"name": name, "params": params, "mode": mode, "unit": a["unit"],
                    "before": b["score"], "beforeErr": b["err"], "after": a["score"], "afterErr": a["err"],
                    "ratio": ratio, "beforeB": b["gc"], "afterB": a["gc"], "beforeP99": b["p99"], "afterP99": a["p99"]})
    return sorted(res, key=lambda r: (r["name"], r["params"]))


def load_summary(path, warmup=60, until=300):
    if not os.path.exists(path):
        return None
    msgs = []
    p99 = []
    bytes_ = []
    cpu = []
    with open(path) as f:
        for r in csv.DictReader(f):
            s = float(r["seconds"])
            if s > warmup and s <= until:
                msgs.append(float(r["msgPerSec"]))
                p99.append(float(r["p99us"]))
                bytes_.append(float(r["allocBytesPerMsg"]))
                cpu.append(float(r["processCpuLoad"]))
    if not msgs:
        return None
    med = sorted(p99)[len(p99) // 2]
    return {"msg": sum(msgs) / len(msgs), "p99": med, "bytes": sum(bytes_) / len(bytes_), "cpu": 100 * sum(cpu) / len(cpu)}


def main():
    data = {}
    classes = ["GroovyExpressionTest", "GroovyCollectionTest", "GroovyRouteTest", "GroovyOverheadTest",
               "GroovyScriptCacheTest", "GroovyJsonDataFormatTest", "GroovyXmlDataFormatTest", "GroovyFirstEvaluationTest"]
    for c in classes:
        before = rows(f"{RAW}/{c}-jdk21.jmh.json")
        before.update(rows(f"{RAW}/{c}-jdk21-quickjs-baseline.jmh.json"))
        after = rows(f"{RAW}/{c}-jdk21-allfixes.jmh.json")
        data[c] = compare(before, after)
    data["GroovyRouteTest-sample"] = compare(rows(f"{RAW}/GroovyRouteTest-jdk21-sample.jmh.json"),
                                             rows(f"{RAW}/GroovyRouteTest-jdk21-allfixes-sample.jmh.json"))
    loads = {}
    pairs = {"java": ("java-harness2", "java-allfixes"), "groovy": ("groovy-harness2", "groovy-allfixes"),
             "quickjs": ("quickjs-baseline-main", "quickjs-allfixes-v2"), "jactl": ("jactl", "jactl-allfixes"),
             "mvel": ("mvel", "mvel-allfixes"), "javaLanguage": ("javaLanguage", "javaLanguage-allfixes"),
             "js": ("js", "js-allfixes"), "groovyManyScripts": ("groovyManyScripts", "groovyManyScripts-allfixes"),
             "groovyPrototype": ("groovy-harness2", "groovy-prototype")}
    for k, (b, a) in pairs.items():
        loads[k] = {"before": load_summary(f"{RAW}/load/GroovyLoadTest-{b}.csv"),
                    "after": load_summary(f"{RAW}/load/GroovyLoadTest-{a}.csv")}
    data["load"] = loads
    out = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdout"
    with open(out, "w") as f:
        json.dump(data, f, indent=1)
    # short console summary
    for c in classes + ["GroovyRouteTest-sample"]:
        for r in data[c]:
            if r["ratio"] is not None:
                print(f"{c:28s} {r['name']:34s} {r['params']:24s} {r['before']:>14,.1f} -> {r['after']:>14,.1f} {r['unit']:6s} x{r['ratio']:.2f}")
    for k, v in loads.items():
        b, a = v["before"], v["after"]
        if b and a:
            print(f"load {k:18s} {b['msg']:>12,.0f} -> {a['msg']:>12,.0f} msg/s x{a['msg']/b['msg']:.2f}  p99 {b['p99']:.0f} -> {a['p99']:.0f} µs  B/msg {b['bytes']:.0f} -> {a['bytes']:.0f}")


if __name__ == "__main__":
    main()
