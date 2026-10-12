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
"""Draws one SVG line chart per metric from GroovyLoadTest CSV files (no third-party libraries).

usage: load_charts.py [--log] <output dir> GroovyLoadTest-java.csv GroovyLoadTest-groovy.csv ...

--log draws the y axis on a log10 scale, for variants that differ by orders of magnitude.
"""
import csv
import math
import os
import sys

METRICS = [
    ("msgPerSec", "Throughput", "msg/s"),
    ("p99us", "Latency p99", "us"),
    ("allocMBPerSec", "Allocation rate", "MB/s"),
    ("allocBytesPerMsg", "Allocation per message", "bytes"),
    ("oldGenAfterGcMB", "Old generation after last GC", "MB"),
    ("heapUsedMB", "Heap used (sampled)", "MB"),
    ("gcPauses", "GC pauses per interval", "count"),
    ("gcPauseTotalMs", "GC pause time per interval", "ms"),
    ("gcPauseMaxMs", "Max GC pause per interval", "ms"),
    ("metaspaceMB", "Metaspace used", "MB"),
    ("classesLoadedTotal", "Classes loaded (total)", "classes"),
    ("processCpuLoad", "Process CPU load", "0..1"),
]
COLORS = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4b5563"]
W, H, L, R, T, B = 760, 300, 80, 170, 36, 40


def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def label(path):
    name = os.path.basename(path).replace("GroovyLoadTest-", "").replace(".csv", "")
    return name


def chart(metric, title, unit, series, log=False):
    xs = [float(r["seconds"]) for _, rows in series for r in rows]
    ys = [float(r[metric]) for _, rows in series for r in rows]
    if not xs:
        return None
    xmax = max(xs) or 1
    sx = lambda x: L + (W - L - R) * x / xmax
    if log:
        positive = [y for y in ys if y > 0]
        if not positive:
            return None
        lo = math.floor(math.log10(min(positive)))
        hi = math.ceil(math.log10(max(positive)))
        if hi == lo:
            hi += 1
        # values <= 0 are drawn on the bottom axis
        sy = lambda y: T + (H - T - B) * (1 - (math.log10(y) - lo) / (hi - lo)) if y > 0 else H - B
        ticks = [10 ** e for e in range(lo, hi + 1)]
        title += " — log scale"
    else:
        ymax = max(ys) * 1.1 or 1
        sy = lambda y: T + (H - T - B) * (1 - y / ymax)
        ticks = [ymax * i / 4 for i in range(5)]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="{L}" y="20" font-size="14" font-weight="bold">{title} ({unit})</text>']
    for y in ticks:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(y):.1f}" y2="{sy(y):.1f}" stroke="#e5e7eb"/>')
        out.append(f'<text x="{L - 6}" y="{sy(y) + 4:.1f}" text-anchor="end" fill="#6b7280">{y:,.4g}</text>')
    for i in range(6):
        x = xmax * i / 5
        out.append(f'<text x="{sx(x):.1f}" y="{H - B + 16}" text-anchor="middle" fill="#6b7280">{x:.0f}s</text>')
    for n, (name, rows) in enumerate(series):
        color = COLORS[n % len(COLORS)]
        pts = " ".join(f"{sx(float(r['seconds'])):.1f},{sy(float(r[metric])):.1f}" for r in rows)
        out.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>')
        out.append(f'<rect x="{W - R + 12}" y="{T + n * 18}" width="12" height="3" fill="{color}"/>')
        out.append(f'<text x="{W - R + 30}" y="{T + n * 18 + 5}">{name}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main(outdir, files, log=False):
    os.makedirs(outdir, exist_ok=True)
    series = [(label(p), load(p)) for p in files]
    for metric, title, unit in METRICS:
        svg = chart(metric, title, unit, series, log)
        if svg:
            with open(os.path.join(outdir, f"{metric}.svg"), "w") as f:
                f.write(svg)
            print(os.path.join(outdir, f"{metric}.svg"))


if __name__ == "__main__":
    args = sys.argv[1:]
    use_log = "--log" in args
    args = [a for a in args if a != "--log"]
    main(args[0], args[1:], use_log)
