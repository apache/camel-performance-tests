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
"""Steady-state summary of GroovyLoadTest CSV files as one Markdown table.

usage: load_tables.py [--warmup 60] GroovyLoadTest-java.csv GroovyLoadTest-groovy.csv ...

Rows with seconds <= warmup are excluded. msg/s and bytes/msg are per sent message.
p99 is reported as the median and the max of the per-interval p99 values.
"""
import csv
import os
import statistics
import sys


def summarise(path, warmup, until=None):
    with open(path) as f:
        rows = [r for r in csv.DictReader(f)]
    prev = 0.0
    steady = []
    for r in rows:
        s = float(r["seconds"])
        r["_interval"] = s - prev
        prev = s
        if s > warmup and (until is None or s <= until):
            steady.append(r)
    if not steady:
        return None
    f = lambda r, k: float(r[k])
    seconds = sum(r["_interval"] for r in steady)
    msgs = sum(f(r, "msgPerSec") * r["_interval"] for r in steady)
    alloc = sum(f(r, "allocMBPerSec") * r["_interval"] for r in steady) * 1024 * 1024
    p99 = [f(r, "p99us") for r in steady]
    return {
        "variant": os.path.basename(path).replace("GroovyLoadTest-", "").replace(".csv", ""),
        "msg/s": msgs / seconds,
        "p99 µs (median/max)": f"{statistics.median(p99):.0f} / {max(p99):.0f}",
        "bytes/msg": alloc / msgs if msgs else 0,
        "alloc MB/s": alloc / seconds / 1024 / 1024,
        "GC pauses/s": sum(f(r, "gcPauses") for r in steady) / seconds,
        "pause %": sum(f(r, "gcPauseTotalMs") for r in steady) / (seconds * 1000) * 100,
        "max pause ms": max(f(r, "gcPauseMaxMs") for r in steady),
        "old gen after GC MB (first/max/last)": "{:.1f} / {:.1f} / {:.1f}".format(
            f(steady[0], "oldGenAfterGcMB"), max(f(r, "oldGenAfterGcMB") for r in steady), f(steady[-1], "oldGenAfterGcMB")),
        "Metaspace MB (first/last)": "{:.1f} / {:.1f}".format(f(steady[0], "metaspaceMB"), f(steady[-1], "metaspaceMB")),
        "classes loaded": int(f(steady[-1], "classesLoadedTotal") - f(steady[0], "classesLoadedTotal")),
        "classes unloaded": int(f(steady[-1], "classesUnloadedTotal") - f(steady[0], "classesUnloadedTotal")),
        "CPU %": statistics.mean(f(r, "processCpuLoad") for r in steady) * 100,
    }


def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"


def main(argv):
    warmup = 60
    until = None
    while argv and argv[0] in ("--warmup", "--until"):
        if argv[0] == "--warmup":
            warmup = float(argv[1])
        else:
            until = float(argv[1])
        argv = argv[2:]
    results = [s for s in (summarise(p, warmup, until) for p in argv) if s]
    if not results:
        return
    keys = list(results[0].keys())
    print("| " + " | ".join(keys) + " |")
    print("|---" + "|---:" * (len(keys) - 1) + "|")
    for r in results:
        print("| " + " | ".join(fmt(r[k]) for k in keys) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
