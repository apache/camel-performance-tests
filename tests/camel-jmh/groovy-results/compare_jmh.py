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
"""Before/after table of two JMH JSON results (for example baseline vs prototype) as Markdown.

usage: compare_jmh.py before.jmh.json after.jmh.json [benchmark name regexp]

Rows are matched on benchmark method, mode and @Param values; rows present only in one file are skipped.
The ratio is after/before for throughput and before/after for time modes, so > 1 always means faster.
"""
import json
import re
import sys


def load(path, rx):
    with open(path) as f:
        text = f.read()
    if not text.strip():
        sys.exit(f"{path} is empty (JMH writes the file when the run completes)")
    rows = {}
    for b in json.loads(text):
        name = b["benchmark"].rsplit(".", 1)[-1]
        if not rx.search(name):
            continue
        params = ",".join(f"{k}={v}" for k, v in sorted(b.get("params", {}).items()))
        pm = b["primaryMetric"]
        alloc = b.get("secondaryMetrics", {}).get("gc.alloc.rate.norm", {}).get("score")
        rows[(name, b["mode"], params)] = (pm["score"], pm["scoreError"], pm["scoreUnit"], alloc)
    return rows


TIME_UNITS = [("s/op", 1.0), ("ms/op", 1e-3), ("us/op", 1e-6), ("ns/op", 1e-9)]


def readable(score, error, unit):
    """Rescales time units (s/op, ms/op, us/op) so the score is >= 1, throughput is left as is."""
    seconds = dict(TIME_UNITS).get(unit)
    if seconds is None:
        return score, error, unit
    for name, factor in TIME_UNITS:
        if score * seconds / factor >= 1 or name == "ns/op":
            return score * seconds / factor, error * seconds / factor, name


def fmt(score, error):
    digits = 0 if score >= 100 else 2
    return f"{score:,.{digits}f} ± {error:,.{digits}f}"


def main(before_path, after_path, pattern="."):
    rx = re.compile(pattern)
    before, after = load(before_path, rx), load(after_path, rx)
    print("| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |")
    print("|---|---|---|---|---|---|---|---|---|")
    for key in sorted(after):
        if key not in before:
            continue
        name, mode, params = key
        b, a = before[key], after[key]
        ratio = a[0] / b[0] if mode == "thrpt" else b[0] / a[0]
        # rescale both sides to the unit that suits the "after" score
        bscore, berror, _ = readable(b[0], b[1], b[2])
        ascore, aerror, unit = readable(a[0], a[1], a[2])
        if unit != b[2]:
            factor = dict(TIME_UNITS)[b[2]] / dict(TIME_UNITS)[unit]
            bscore, berror = b[0] * factor, b[1] * factor
        balloc = f"{b[3]:,.0f}" if b[3] is not None else ""
        aalloc = f"{a[3]:,.0f}" if a[3] is not None else ""
        print(f"| `{name}` | {params} | {mode} | {unit} | {fmt(bscore, berror)} | {fmt(ascore, aerror)} | {ratio:.2f}× | {balloc} | {aalloc} |")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
