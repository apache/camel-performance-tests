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
# Follow-up: groovy evaluation gets slower every iteration with 1,000 cached scripts
# (GroovyScriptCacheTest.roundRobinDistinctScripts, distinctScripts=1000: 3.0 -> 11.4 us/op over 50 s, no recompilation).
#
#   ASYNC_PROFILER=/path/libasyncProfiler.dylib ./groovy-results/run-groovy-followups.sh
set -euo pipefail

cd "$(dirname "$0")/.."
JDK21=${JDK21:-$HOME/.sdkman/candidates/java/21.0.10-tem}
RESULTS=${RESULTS:-$(pwd)/groovy-results/raw}
LIB=${ASYNC_PROFILER:?set ASYNC_PROFILER to libasyncProfiler}
OUT="$RESULTS/followup-cache1000"
INCLUDE='org.apache.camel.itest.jmh.groovy.GroovyScriptCacheTest.roundRobinDistinctScripts$'
mkdir -p "$RESULTS/logs" "$RESULTS/load" "$OUT/flame"

run() {
  # run <suffix> <test class> [extra maven args...]
  local suffix=$1 test=$2
  shift 2
  echo "=== $(date '+%H:%M:%S') $test $suffix $*"
  if ! JAVA_HOME=$JDK21 mvn -q test -P jmh -Dtest="$test" -Dsurefire.failIfNoSpecifiedTests=false \
      -Djmh.resultDir="$RESULTS" -Djmh.suffix="$suffix" "$@" > "$RESULTS/logs/$test$suffix.log" 2>&1; then
    echo "FAILED $test $suffix (see $RESULTS/logs/$test$suffix.log)"
  fi
}

# 1. does the slowdown level off? 20 x 2 s measurement iterations, 2 forks, all K (100 / 1000 / 1001 / 2000)
run -jdk21-cache-long GroovyScriptCacheTest -Djmh.modes=avgt -Djmh.i=20 "-Djmh.include=$INCLUDE" "-Djmh.prof=gc|cl"

# 2. JIT and code cache: one JFR recording per fork (deoptimizations, compilations, code cache), code cache printed at exit
run -jdk21-cache-jfr GroovyScriptCacheTest -Djmh.modes=avgt -Djmh.forks=1 -Djmh.i=10 "-Djmh.include=$INCLUDE" \
  "-Djmh.jvmArgs=-Xms2g -Xmx2g -XX:+UnlockDiagnosticVMOptions -XX:+PrintCodeCache -XX:StartFlightRecording=filename=$OUT/cache-%p.jfr,settings=profile"

# 3. where the CPU goes: async-profiler cpu flamegraph per K
run -jdk21-cache-flame GroovyScriptCacheTest -Djmh.modes=avgt -Djmh.forks=1 -Djmh.i=10 "-Djmh.include=$INCLUDE" \
  "-Djmh.prof=async:libPath=$LIB;output=flamegraph,collapsed;event=cpu;dir=$OUT/flame"

# 4. does a long-running route degrade the same way? 5 minutes, 900 distinct setBody scripts (all cached)
label=groovyManyScripts-900scripts
run -900scripts GroovyLoadTest -Dload.variant=groovyManyScripts -Dload.scripts=900 -Dload.duration=300 \
  -Djmh.resultDir="$RESULTS/load" \
  "-DargLine=-Xms1g -Xmx1g -Xlog:gc*,safepoint:file=$RESULTS/load/$label-gc.log:time,uptime,level,tags -XX:StartFlightRecording=filename=$RESULTS/load/$label.jfr,settings=profile"

echo "=== $(date '+%H:%M:%S') phase followup-cache1000 done"

# 5. collapsed stacks for the report ("top frames with percentages"); the flamegraphs phase only wrote HTML
PKG=org.apache.camel.itest.jmh.groovy
COLLAPSED="$RESULTS/flamegraphs-collapsed"
for event in cpu alloc; do
  for include in 'GroovyExpressionTest.concat(Groovy|JavaExpression)$' 'GroovyRouteTest.(groovy|java)Route1Thread$' \
                 'GroovyJsonDataFormatTest.marshalGroovyPretty$' 'GroovyXmlDataFormatTest.(unmarshalGroovyXml|marshalMapGroovyXml)$'; do
    name=$(echo "$include" | tr -c 'A-Za-z0-9\n' '_')
    mkdir -p "$COLLAPSED/$event"
    run "-collapsed-$event-$name" "${include%%.*}" -Djmh.forks=1 -Djmh.wi=3 -Djmh.i=2 -Djmh.r=5 -Djmh.modes=avgt \
      "-Djmh.include=$PKG.$include" "-Djmh.prof=async:libPath=$LIB;output=collapsed;event=$event;dir=$COLLAPSED/$event"
  done
done
for event in cpu lock; do
  mkdir -p "$COLLAPSED/$event-8threads"
  run "-collapsed-$event-route8threads" GroovyRouteTest -Djmh.forks=1 -Djmh.wi=3 -Djmh.i=2 -Djmh.r=5 -Djmh.modes=thrpt \
    "-Djmh.include=$PKG.GroovyRouteTest.(groovy|java)Route8Threads$" \
    "-Djmh.prof=async:libPath=$LIB;output=collapsed;event=$event;dir=$COLLAPSED/$event-8threads"
done
echo "=== $(date '+%H:%M:%S') phase followup-collapsed done"
