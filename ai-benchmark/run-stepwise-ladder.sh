#!/bin/zsh
# Runs the round-2 stepwise set: every steps-ladder/<name>.json, each from a fresh project, k times.
# Usage: run-stepwise-ladder.sh <tag> [k]      Results: stepwise/<tag>-<i>/<name>/ (results.json, run.log, traces)
# BENCH_REFERENCE=1 applies the reference files instead of asking the model (the reference pass of the steps files).
# BENCH_NEGATIVE=1 writes nothing, so each step is scored on the step before it (the negative pass: every step must fail).
# BENCH_ONLY="<name> [<name> ...]" runs only those examples.
# BENCH_STEPS_DIR=steps-new runs the new set (2026-10-18) instead of the ladder in steps-ladder/.
set -u
TAG="${1:?usage: run-stepwise-ladder.sh <tag> [k]}"
K="${2:-1}"
cd "$(dirname "$0")"
export MCP_URL="${MCP_URL:-http://127.0.0.1:9090/mcp}"
command -v caffeinate > /dev/null && caffeinate -i -s -w $$ &
for i in $(seq 1 "$K"); do
  if (( K > 1 )); then T="$TAG-$i"; else T="$TAG"; fi
  : > "stepwise-$T.log"   # a fresh log per run, so a later wait on its DONE line cannot see an earlier run's
  for f in ${BENCH_STEPS_DIR:-steps-ladder}/*.json; do
    name=$(basename "$f" .json)
    if [[ -n "${BENCH_ONLY:-}" && " $BENCH_ONLY " != *" $name "* ]]; then continue; fi
    python3 gen_stepwise.py "$name" > /dev/null
    echo "[$T] $name start $(date +%T)" | tee -a "stepwise-$T.log"
    BENCH_STEPS="$f" BENCH_TAG="$T/$name" python3 agent_mcp_stepwise.py > "stepwise-$T-$name.out" 2>&1
    tail -1 "stepwise/$T/$name/run.log" | tee -a "stepwise-$T.log"
    # safety net: the harness stops its apps, but an interrupted run leaves one behind (r5: an orphan held port 8080 for
    # six hours and failed every later HTTP rung). Only the harness's apps, the ones that run from its folders, also
    # those the model started with camel_run under another name: another session's apps on this machine stay (Nov 6:
    # `camel stop` with no name stopped every app)
    python3 -c "import agent_mcp_stepwise as h; h.stop_harness_apps()" > /dev/null 2>&1 || true
    sleep 3
    if lsof -nP -iTCP:8080 -sTCP:LISTEN > /dev/null 2>&1; then
      echo "[$T] WARNING port 8080 still in use after $name: $(lsof -nP -iTCP:8080 -sTCP:LISTEN | tail -1)" | tee -a "stepwise-$T.log"
    fi
  done
  # the services an example needed stay up across its passes; stop them once the run is over, only those the harness
  # started (stepwise/infra-started.json): another session may run the same service
  python3 -c "import agent_mcp_stepwise as h; h.infra_stop_started()" > /dev/null 2>&1 || true
  echo "[$T] DONE $(date +%T)" | tee -a "stepwise-$T.log"
done
python3 summarize_stepwise.py "$TAG" "$K"
