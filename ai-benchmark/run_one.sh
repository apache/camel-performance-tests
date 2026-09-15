#!/bin/zsh
# Usage: run_one.sh <folder> <seconds> [probe command]
# Validates every *.camel.yaml in <folder> with `camel validate yaml`, then runs the
# folder for <seconds> and captures the log. Optional probe runs 6s after start.
set -u
folder="$1"; secs="$2"; probe="${3:-}"
cd "$folder" || exit 2
: > validate.log; : > run.log; : > probe.log
files=(*.camel.yaml(N) *.yaml(N))
if (( ${#files} == 0 )); then echo "no yaml files" > validate.log; fi
for f in ${(u)files}; do
  echo "### $f" >> validate.log
  camel validate yaml "$f" >> validate.log 2>&1
  echo "exit=$?" >> validate.log
done
# properties files: camel.* keys against the catalog (camel validate properties, CAMEL-24698)
if [[ "${BENCH_VALIDATE_SOURCE:-0}" == "1" ]]; then
  for p in *.java(N) *.xsl(N) *.xslt(N) *.xml(N); do
    echo "### $p" >> validate.log
    camel validate source "$p" >> validate.log 2>&1
    echo "exit=$?" >> validate.log
  done
fi
if [[ "${BENCH_VALIDATE_PROPS:-0}" == "1" ]]; then
  for p in *.properties(N); do
    echo "### $p" >> validate.log
    camel validate properties "$p" >> validate.log 2>&1
    echo "exit=$?" >> validate.log
  done
fi
# run everything in the folder (yaml, java, properties are picked up by camel run *)
( camel run * --max-seconds="$secs" --logging-color=false > run.log 2>&1 ) &
pid=$!
# watchdog: a camel.main.durationMaxSeconds in the example's own application.properties overrides --max-seconds
# (run 9 memory-leak ran for an hour); kill the run after the expected time plus a grace period
( sleep $((secs + 45)); pkill -TERM -f -- "--max-seconds=$secs --logging-color=false" 2>/dev/null; kill -TERM $pid 2>/dev/null ) &
watchdog=$!
if [[ -n "$probe" ]]; then
  sleep 7
  eval "$probe" > probe.log 2>&1
fi
wait $pid
echo "run-exit=$?" >> run.log
kill $watchdog 2>/dev/null
