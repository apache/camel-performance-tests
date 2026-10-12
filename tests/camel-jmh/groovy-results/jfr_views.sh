#!/usr/bin/env bash
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
# Summarises the GroovyLoadTest JFR recordings with `jfr view` (JDK 21+):
#
#   ./groovy-results/jfr_views.sh groovy-results/raw/load/*.jfr
#
# writes <recording>.views.txt next to each recording
set -euo pipefail

JFR=${JFR:-$HOME/.sdkman/candidates/java/21.0.10-tem/bin/jfr}
for recording in "$@"; do
  out=${recording%.jfr}.views.txt
  {
    for view in gc-configuration gc-pauses gc gc-references allocation-by-class allocation-by-site allocation-by-thread \
                hot-methods contention-by-site memory-leaks-by-class longest-compilations class-loaders; do
      echo "##### jfr view $view"
      "$JFR" view --width 200 "$view" "$recording" 2>&1 || true
      echo
    done
  } > "$out"
  echo "$out"
done
