#!/usr/bin/env python3
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Turns JMH JSON result files into Markdown tables.

usage: jmh_tables.py result.jmh.json [more.jmh.json ...]

Scores are normalised to ops/s (thrpt) and ns/op (avgt, sample, ss). The error is the 99.9% confidence
half-width reported by JMH. Allocation is gc.alloc.rate.norm (bytes/op) when -prof gc was used.
The ratio column compares against the first benchmark of the same group (same mode and params) whose
name contains "java", "Jackson" or "Dom"; lower-is-better modes report time ratio, thrpt reports slowdown.
"""
import json
import re
import sys
from collections import OrderedDict

TIME_FACTORS = {"s": 1e9, "ms": 1e6, "us": 1e3, "ns": 1.0}


def normalise(mode, score, unit):
    if mode == "thrpt":
        # ops/<unit>
        per = unit.split("/")[1]
        return score * (1e9 / TIME_FACTORS[per]), "ops/s"
    # <unit>/op
    base = unit.split("/")[0]
    return score * TIME_FACTORS[base], "ns/op"


def fmt(value):
    if value is None:
        return ""
    if value == 0:
        return "0"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


# benchmark name pattern -> baseline candidates (first one present in the same group wins)
BASELINES = [
    (r"^concat", ["concatJavaExpression"]),
    (r"^arithmetic", ["arithmeticJavaExpression"]),
    (r"^predicate", ["predicateJava"]),
    (r"Route1Thread$", ["javaRoute1Thread"]),
    (r"Route8Threads$", ["javaRoute8Threads"]),
    (r"^firstEvaluation", ["firstEvaluationJava"]),
    (r"^unmarshalWalk", ["unmarshalWalkJackson"]),
    (r"^unmarshal", ["unmarshalJackson", "unmarshalDom"]),
    (r"^marshalMap", ["marshalMapJacksonXml"]),
    (r"^marshal", ["marshalJacksonCompact"]),
    (r"^(javaStreams|groovy|precompiled|jactl|javaLanguage|mvel|js|python3)", ["javaStreams"]),
]


def baseline_for(name, names):
    for pattern, candidates in BASELINES:
        if re.search(pattern, name):
            for c in candidates:
                if c in names:
                    return c
            return None
    return None


def main(files):
    for path in files:
        with open(path) as f:
            results = json.load(f)
        groups = OrderedDict()
        for r in results:
            name = r["benchmark"].split(".")[-1]
            mode = r["mode"]
            params = ",".join(f"{k}={v}" for k, v in (r.get("params") or {}).items())
            m = r["primaryMetric"]
            score, unit = normalise(mode, m["score"], m["scoreUnit"])
            err = m.get("scoreError")
            err = normalise(mode, err, m["scoreUnit"])[0] if isinstance(err, (int, float)) else None
            alloc = r.get("secondaryMetrics", {}).get("gc.alloc.rate.norm", {}).get("score")
            pct = m.get("scorePercentiles", {})
            p99 = normalise(mode, pct["99.0"], m["scoreUnit"])[0] if mode == "sample" and "99.0" in pct else None
            groups.setdefault((mode, params), []).append((name, score, err, unit, alloc, r["threads"], p99))

        print(f"\n### {path.split('/')[-1]}\n")
        for (mode, params), rows in groups.items():
            names = [row[0] for row in rows]
            scores = {row[0]: row[1] for row in rows}
            title = f"mode={mode}" + (f", {params}" if params else "")
            print(f"\n{title}\n")
            header = "| benchmark | threads | score | ± error (99.9%) | unit | alloc bytes/op |"
            sep = "|---|---:|---:|---:|---|---:|"
            if mode == "sample":
                header += " p99 ns/op |"
                sep += "---:|"
            header += " baseline | slowdown vs baseline |"
            sep += "---|---:|"
            print(header)
            print(sep)
            for name, score, err, unit, alloc, threads, p99 in rows:
                line = f"| {name} | {threads} | {fmt(score)} | {fmt(err)} | {unit} | {fmt(alloc)} |"
                if mode == "sample":
                    line += f" {fmt(p99)} |"
                base = baseline_for(name, names)
                if base and scores.get(base):
                    # >1 means slower than the baseline for both throughput and time modes
                    ratio = scores[base] / score if mode == "thrpt" else score / scores[base]
                    line += f" {base} | {ratio:.2f}x |"
                else:
                    line += " | |"
                print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
