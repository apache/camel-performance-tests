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
# Runs the camel-groovy benchmarks sequentially (never run two at once, they share the CPU).
#
#   ./groovy-results/run-groovy-benchmarks.sh <phase> [<phase> ...]
#
# phases:
#   load         long running high load (heap behaviour), 5 min per variant (LOAD_DURATION), GC log + JFR
#   jdk21        all JMH benchmarks on JDK 21 (thrpt+avgt, -prof gc)
#   flamegraphs  async-profiler cpu/alloc flamegraphs (+ cpu/lock with 8 threads)
#   churn        script cache churn harness (default and SoftRefLRUPolicyMSPerMB=0)
#   prototype    re-runs the groovy benchmarks and load against camel-groovy 4.23.0-perf-SNAPSHOT
#   groovy6      groovy variants with Groovy 5.1.2 and 6.0.0-RC-1
#   jdk17 jdk25  expression/collection/route/overhead/first-evaluation on JDK 17 / 25 (thrpt)
#   quickjs-baseline  only the quickjs benchmarks (expression/collection/route thrpt -prof gc, first-evaluation) on
#                JDK 21, suffix -jdk21-quickjs-baseline, then the quickjs load run (suffix -baseline)
#   features     FeatureRoutes (every quickjs feature, same logic per language) load runs: unbounded and 100 msg/s
#   allfixes     the jdk21 phase again with suffix -jdk21-allfixes (Camel build with all fixes applied), then the load
#                runs of java/groovy/quickjs/jactl/mvel/javaLanguage/js and groovyManyScripts with suffix -allfixes
#   all          all of the above in that order
#
# Environment:
#   JDK17/JDK21/JDK25  java homes (defaults: sdkman candidates)
#   ASYNC_PROFILER     path to libasyncProfiler.(so|dylib)
#   CAMEL_DIR          apache/camel checkout with the prototype (prototype phase)
#   RESULTS            output directory (default: groovy-results/raw)
#   LOAD_DURATION      seconds per load run (default 300), LOAD_RATE fixed rate runs (default 100000 msg/s)
set -euo pipefail

cd "$(dirname "$0")/.."
JDK17=${JDK17:-$HOME/.sdkman/candidates/java/17.0.18-amzn}
JDK21=${JDK21:-$HOME/.sdkman/candidates/java/21.0.10-tem}
JDK25=${JDK25:-$HOME/.sdkman/candidates/java/25.0.2-tem}
RESULTS=${RESULTS:-$(pwd)/groovy-results/raw}
PROTOTYPE_VERSION=${PROTOTYPE_VERSION:-4.23.0-perf-SNAPSHOT}
PKG=org.apache.camel.itest.jmh.groovy
mkdir -p "$RESULTS/logs"

run() {
  # run <java home> <suffix> <test class> [extra maven args...]
  local home=$1 suffix=$2 test=$3
  shift 3
  echo "=== $(date '+%H:%M:%S') $test $suffix $*"
  if ! JAVA_HOME=$home mvn -q test -P jmh -Dtest="$test" -Dsurefire.failIfNoSpecifiedTests=false \
      -Djmh.resultDir="$RESULTS" -Djmh.suffix="$suffix" "$@" > "$RESULTS/logs/$test$suffix.log" 2>&1; then
    echo "FAILED $test $suffix (see $RESULTS/logs/$test$suffix.log)"
  fi
}

load() {
  # load <variant> <rate or empty> <label suffix> [extra maven args...]
  local variant=$1 rate=$2 suffix=$3
  shift 3
  local label=$variant${rate:+-rate$rate}$suffix
  mkdir -p "$RESULTS/load"
  # 300 s: steady-state averages over 60-300 s matched 60-600 s within 1% (tails and full-GC cycles need longer runs)
  run "$JDK21" "$suffix" GroovyLoadTest -Dload.variant="$variant" -Dload.duration="${LOAD_DURATION:-300}" \
    ${rate:+-Dload.rate=$rate} -Djmh.resultDir="$RESULTS/load" \
    "-DargLine=-Xms1g -Xmx1g -Xlog:gc*,safepoint:file=$RESULTS/load/$label-gc.log:time,uptime,level,tags -XX:StartFlightRecording=filename=$RESULTS/load/$label.jfr,settings=profile" \
    "$@"
}

phase() {
  case $1 in
    load)
      local rate=${LOAD_RATE:-100000}
      load java "" ""
      load groovy "" ""
      load groovyPrototype "" ""
      load groovyManyScripts "" ""
      load java "$rate" ""
      load groovy "$rate" ""
      ;;
    jdk21)
      run "$JDK21" -jdk21 GroovyExpressionTest -Djmh.prof=gc
      run "$JDK21" -jdk21 GroovyCollectionTest -Djmh.prof=gc
      run "$JDK21" -jdk21 GroovyRouteTest -Djmh.prof=gc
      run "$JDK21" -jdk21-sample GroovyRouteTest -Djmh.modes=sample
      run "$JDK21" -jdk21 GroovyOverheadTest -Djmh.prof=gc
      run "$JDK21" -jdk21 GroovyFirstEvaluationTest
      run "$JDK21" -jdk21 GroovyScriptCacheTest "-Djmh.prof=gc|cl"
      run "$JDK21" -jdk21 GroovyJsonDataFormatTest -Djmh.prof=gc
      run "$JDK21" -jdk21 GroovyXmlDataFormatTest -Djmh.prof=gc
      ;;
    flamegraphs)
      local lib=${ASYNC_PROFILER:?set ASYNC_PROFILER to libasyncProfiler}
      local event include name dir
      for event in cpu alloc; do
        for include in 'GroovyExpressionTest.concat(Groovy|JavaExpression)$' 'GroovyRouteTest.(groovy|java)Route1Thread$' \
                       'GroovyJsonDataFormatTest.marshalGroovyPretty$' 'GroovyXmlDataFormatTest.(unmarshalGroovyXml|marshalMapGroovyXml)$'; do
          name=$(echo "$include" | tr -c 'A-Za-z0-9\n' '_')
          dir="$RESULTS/flamegraphs/$event"
          mkdir -p "$dir"
          run "$JDK21" "-flame-$event-$name" "${include%%.*}" -Djmh.forks=1 -Djmh.i=3 -Djmh.r=5 -Djmh.modes=avgt \
            "-Djmh.include=$PKG.$include" "-Djmh.prof=async:libPath=$lib;output=flamegraph;event=$event;dir=$dir"
        done
      done
      # 8 threads: where does the groovy route stop scaling (cpu and lock contention)
      for event in cpu lock; do
        dir="$RESULTS/flamegraphs/$event-8threads"
        mkdir -p "$dir"
        run "$JDK21" "-flame-$event-route8threads" GroovyRouteTest -Djmh.forks=1 -Djmh.i=3 -Djmh.r=5 -Djmh.modes=thrpt \
          "-Djmh.include=$PKG.GroovyRouteTest.(groovy|java)Route8Threads$" \
          "-Djmh.prof=async:libPath=$lib;output=flamegraph;event=$event;dir=$dir"
      done
      ;;
    churn)
      run "$JDK21" -jdk21 GroovyScriptCacheChurnTest
      run "$JDK21" -jdk21-softref0 GroovyScriptCacheChurnTest -DargLine=-XX:SoftRefLRUPolicyMSPerMB=0
      ;;
    prototype)
      CAMEL_DIR=${CAMEL_DIR:?set CAMEL_DIR} bash "$(dirname "$0")/install-prototype.sh" 2>&1 | tail -1
      local v=-Dcamel-groovy-bench-version=$PROTOTYPE_VERSION
      run "$JDK21" -jdk21-prototype GroovyExpressionTest "$v" -Djmh.prof=gc "-Djmh.include=$PKG.GroovyExpressionTest.(concat|arithmetic|predicate)Groovy$"
      run "$JDK21" -jdk21-prototype GroovyCollectionTest "$v" -Djmh.prof=gc "-Djmh.include=$PKG.GroovyCollectionTest.groovy(Dynamic|CompileStatic)$"
      run "$JDK21" -jdk21-prototype GroovyRouteTest "$v" -Djmh.prof=gc "-Djmh.include=$PKG.GroovyRouteTest.groovyRoute.*"
      run "$JDK21" -jdk21-prototype GroovyOverheadTest "$v" -Djmh.prof=gc "-Djmh.include=$PKG.GroovyOverheadTest.evaluateGroovy$"
      run "$JDK21" -jdk21-prototype GroovyScriptCacheTest "$v" "-Djmh.prof=gc|cl" "-Djmh.include=$PKG.GroovyScriptCacheTest.roundRobinDistinctScripts$"
      load groovy "" -prototype "$v"
      load groovyManyScripts "" -prototype "$v"
      ;;
    groovy6)
      # one include per test class: jmh.include replaces the class filter, so a regex matching all three classes
      # would run every groovy benchmark once per class
      local gv
      for gv in 5.1.2 6.0.0-RC-1; do
        run "$JDK21" "-jdk21-groovy-$gv" GroovyExpressionTest -Djmh.modes=thrpt -Dgroovy-bench-version=$gv \
          "-Djmh.include=$PKG.GroovyExpressionTest.*Groovy$"
        run "$JDK21" "-jdk21-groovy-$gv" GroovyCollectionTest -Djmh.modes=thrpt -Dgroovy-bench-version=$gv \
          "-Djmh.include=$PKG.GroovyCollectionTest.(groovy|precompiled).*"
        run "$JDK21" "-jdk21-groovy-$gv" GroovyRouteTest -Djmh.modes=thrpt -Dgroovy-bench-version=$gv \
          "-Djmh.include=$PKG.GroovyRouteTest.groovy.*"
      done
      ;;
    languages-load)
      # jactl, java (jOOR), mvel, js (GraalJS), python3 (GraalPy) with the same route and load as java/groovy
      local v
      for v in jactl javaLanguage mvel js python3; do
        load "$v" "" ""
      done
      ;;
    jdk17|jdk25)
      local home=$JDK17 t args=()
      # GraalJS / GraalPy need native access on JDK 24+
      [ "$1" = jdk25 ] && home=$JDK25 && args=("-Djmh.jvmArgs=-Xms2g -Xmx2g --enable-native-access=ALL-UNNAMED")
      # first evaluation (10 cold forks x 20 iterations per language) only runs on JDK 21
      for t in GroovyExpressionTest GroovyRouteTest; do
        # ${args[@]+...}: bash 3.2 (macOS) treats an empty array as unbound under set -u
        run "$home" "-$1" $t -Djmh.modes=thrpt -Djmh.prof=gc ${args[@]+"${args[@]}"}
      done
      ;;
    quickjs-baseline)
      # one include per test class (jmh.include replaces the class filter, see groovy6); the regex is unanchored
      run "$JDK21" -jdk21-quickjs-baseline GroovyExpressionTest -Djmh.modes=thrpt -Djmh.prof=gc \
        "-Djmh.include=$PKG.GroovyExpressionTest.(concat|arithmetic|predicate)Quickjs$"
      run "$JDK21" -jdk21-quickjs-baseline GroovyCollectionTest -Djmh.modes=thrpt -Djmh.prof=gc \
        "-Djmh.include=$PKG.GroovyCollectionTest.quickjs$"
      run "$JDK21" -jdk21-quickjs-baseline GroovyRouteTest -Djmh.modes=thrpt -Djmh.prof=gc \
        "-Djmh.include=$PKG.GroovyRouteTest.quickjsRoute.*"
      run "$JDK21" -jdk21-quickjs-baseline GroovyFirstEvaluationTest \
        "-Djmh.include=$PKG.GroovyFirstEvaluationTest.firstEvaluationQuickjs$"
      load quickjs "" -baseline
      ;;
    features)
      # every quickjs feature in every language (FeatureRoutes): unbounded 5 min, then a fixed 100 msg/s for 3 min so
      # CPU, allocation, heap and latency are comparable at equal traffic
      local v
      for v in java groovy js quickjs jactl mvel python3 python; do
        load "features-$v" "" ""
        LOAD_DURATION=180 load "features-$v" 100 ""
      done
      ;;
    allfixes)
      # the jdk21 phase against a Camel build with all the fixes applied, plus the load runs of every language
      run "$JDK21" -jdk21-allfixes GroovyExpressionTest -Djmh.prof=gc
      run "$JDK21" -jdk21-allfixes GroovyCollectionTest -Djmh.prof=gc
      run "$JDK21" -jdk21-allfixes GroovyRouteTest -Djmh.prof=gc
      run "$JDK21" -jdk21-allfixes-sample GroovyRouteTest -Djmh.modes=sample
      run "$JDK21" -jdk21-allfixes GroovyOverheadTest -Djmh.prof=gc
      run "$JDK21" -jdk21-allfixes GroovyFirstEvaluationTest
      run "$JDK21" -jdk21-allfixes GroovyScriptCacheTest "-Djmh.prof=gc|cl"
      run "$JDK21" -jdk21-allfixes GroovyJsonDataFormatTest -Djmh.prof=gc
      run "$JDK21" -jdk21-allfixes GroovyXmlDataFormatTest -Djmh.prof=gc
      local v
      for v in java groovy quickjs jactl mvel javaLanguage js; do
        load "$v" "" -allfixes
      done
      # 1500 distinct scripts (load.scripts, the default) as in the load phase
      load groovyManyScripts "" -allfixes -Dload.scripts=1500
      ;;
    all)
      for p in load languages-load jdk21 flamegraphs churn prototype groovy6 jdk17 jdk25 quickjs-baseline allfixes; do
        phase $p
      done
      ;;
    *)
      echo "unknown phase $1"; exit 1;;
  esac
  echo "=== $(date '+%H:%M:%S') phase $1 done"
}

for p in "$@"; do
  phase "$p"
done
