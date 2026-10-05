#!/bin/zsh
# Starts or stops the reference stock API server (the openapi-server example, copied to seed/openapi-server-ref by
# gen_ladder.py) on port 8080 for the openapi-client example. Usage: ref-server.sh start|stop
cd "$(dirname "$0")/seed/openapi-server-ref" || exit 2
case "$1" in
  start)
    ( camel run * --logging-color=false > ../../ref-server.log 2>&1 ) &
    for i in $(seq 1 60); do
      curl -s -o /dev/null localhost:8080/api/openapi && { echo "ref server up after ${i}s"; exit 0; }
      sleep 1
    done
    echo "ref server did not come up"; exit 1 ;;
  stop)
    # the server owns port 8080 by definition (jbang forks the java process, so a pattern on the command line misses it)
    lsof -ti :8080 | xargs -r kill -TERM 2>/dev/null; sleep 3
    lsof -ti :8080 | xargs -r kill -KILL 2>/dev/null; echo "ref server stopped" ;;
esac
