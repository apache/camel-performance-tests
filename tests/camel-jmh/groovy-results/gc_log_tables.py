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
"""GC figures for the GroovyLoadTest runs taken from the unified JVM GC logs (-Xlog:gc*), which are the source of
truth: every stop-the-world pause (young, mixed, remark, cleanup, full) with its exact duration, and the heap
occupancy after each young collection.

The harness CSV undercounts pauses (it ignored the "G1 Concurrent GC" MXBean that reports Remark/Cleanup and rounds
GcInfo durations down to whole ms) and its "old gen after GC" column only changes on mixed/full collections; use this
table instead.

usage: gc_log_tables.py [--warmup 60] [--until 300] java-gc.log groovy-gc.log ...

Time is JVM uptime, which starts a few hundred ms before the harness clock; for a 60 s warmup the difference is
negligible.
"""
import os
import re
import sys

# [2026-09-10T13:31:15.310+0200][316.673s][info][gc          ] GC(3000) Pause Young (Normal) (G1 Evacuation Pause) 623M->10M(1024M) 134.449ms
PAUSE = re.compile(r"\]\[(?P<up>[0-9.]+)s\]\[info\]\[gc\s*\] GC\(\d+\) Pause (?P<kind>Young \((?P<young>[^)]*)\)|Remark|Cleanup|Full)"
                   r"(?P<rest>.*?) (?P<before>\d+)M->(?P<after>\d+)M\((?P<cap>\d+)M\) (?P<ms>[0-9.]+)ms$")


def kind_of(m):
    if m.group("kind").startswith("Young"):
        y = m.group("young")
        return "mixed" if y == "Mixed" else "young"
    return m.group("kind").lower()


def summarise(path, warmup, until):
    counts = {}
    total_ms = {}
    max_ms = 0.0
    after_young = []
    first_up = last_up = None
    with open(path) as f:
        for line in f:
            m = PAUSE.search(line)
            if not m:
                continue
            up = float(m.group("up"))
            if up <= warmup or (until is not None and up > until):
                continue
            k = kind_of(m)
            ms = float(m.group("ms"))
            counts[k] = counts.get(k, 0) + 1
            total_ms[k] = total_ms.get(k, 0.0) + ms
            max_ms = max(max_ms, ms)
            if k == "young":
                after_young.append(int(m.group("after")))
            first_up = up if first_up is None else first_up
            last_up = up
    if first_up is None:
        return None
    window = (until if until is not None else last_up) - warmup
    all_ms = sum(total_ms.values())
    n = len(after_young)
    third = max(1, n // 3)
    return {
        "run": os.path.basename(path).replace("-gc.log", ""),
        "window s": f"{warmup:.0f}–{until if until is not None else last_up:.0f}",
        "STW pauses": sum(counts.values()),
        "pauses/s": sum(counts.values()) / window,
        "pause ms total": all_ms,
        "pause %": all_ms / (window * 1000) * 100,
        "max pause ms": max_ms,
        "young": f"{counts.get('young', 0)} / {total_ms.get('young', 0):,.0f} ms",
        "mixed": f"{counts.get('mixed', 0)} / {total_ms.get('mixed', 0):,.0f} ms",
        "remark": f"{counts.get('remark', 0)} / {total_ms.get('remark', 0):,.0f} ms",
        "cleanup": f"{counts.get('cleanup', 0)} / {total_ms.get('cleanup', 0):,.0f} ms",
        "full": f"{counts.get('full', 0)} / {total_ms.get('full', 0):,.0f} ms",
        # average heap occupancy right after young GCs, first third vs last third of the window: growth indicator
        "heap after young GC MB (first ⅓ / last ⅓ avg)": (
            f"{sum(after_young[:third]) / third:.1f} / {sum(after_young[-third:]) / third:.1f}" if n else ""),
    }


def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"


def main(argv):
    warmup, until = 60.0, None
    while argv and argv[0] in ("--warmup", "--until"):
        if argv[0] == "--warmup":
            warmup = float(argv[1])
        else:
            until = float(argv[1])
        argv = argv[2:]
    rows = [r for r in (summarise(p, warmup, until) for p in argv) if r]
    if not rows:
        return
    keys = list(rows[0].keys())
    print("| " + " | ".join(keys) + " |")
    print("|---" * len(keys) + "|")
    for r in rows:
        print("| " + " | ".join(fmt(r[k]) for k in keys) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
