#!/bin/zsh
# Runs the four HTTP rungs of the stepwise ladder (CAMEL-24886): two servers checked with HTTP probes, a client calling a
# server in the same app, and a contract-first client calling a peer app. A wrapper around run-stepwise-ladder.sh.
# Usage: run-http.sh <tag> [k]                       Results: stepwise/<tag>-<i>/<name>/
#        BENCH_REFERENCE=1 run-http.sh <tag>         the reference pass: the steps' own reference files, no model
cd "$(dirname "$0")"
export BENCH_ONLY="connect-stock-api connect-http-client contracts-openapi-server contracts-openapi-client"
exec ./run-stepwise-ladder.sh "$@"
