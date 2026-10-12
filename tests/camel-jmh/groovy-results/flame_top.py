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
"""Summarises async-profiler collapsed stacks (output=collapsed) into top frames with percentages.

usage: flame_top.py collapsed-cpu.csv [top N] [frame filter regexp]

Prints:
  - self (leaf) frames
  - inclusive frames matching the filter (default: Camel and Groovy classes), counted once per stack
"""
import re
import sys
from collections import Counter


def main(path, top=15, pattern=r"org\.apache\.camel|groovy|org\.codehaus\.groovy|org\.apache\.groovy"):
    selfc = Counter()
    inclusive = Counter()
    total = 0
    rx = re.compile(pattern)
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            stack, _, count = line.rpartition(" ")
            try:
                n = int(count)
            except ValueError:
                continue
            frames = stack.split(";")
            total += n
            selfc[frames[-1]] += n
            for frame in set(frames):
                if rx.search(frame):
                    inclusive[frame] += n
    print(f"{path}: {total} samples")
    print(f"\ntop {top} self frames")
    for frame, n in selfc.most_common(top):
        print(f"  {100.0 * n / total:5.1f}%  {frame}")
    print(f"\ntop {top} inclusive frames matching /{pattern}/")
    for frame, n in inclusive.most_common(top):
        print(f"  {100.0 * n / total:5.1f}%  {frame}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[0], int(args[1]) if len(args) > 1 else 15, *(args[2:3]))
