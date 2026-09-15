#!/bin/zsh
# Starts the Camel MCP server with HTTP transport on port 9090 (camel mcp --http) and waits until it answers.
# Set CAMEL_MCP_JAR to run a locally built camel-jbang-mcp runner jar instead of the CLI plugin.
cd "$(dirname "$0")"
PORT="${MCP_PORT:-9090}"
pkill -f "camel-jbang-mcp.*runner.jar" 2>/dev/null; pkill -f "camel mcp --http" 2>/dev/null; sleep 1
if [[ -n "${CAMEL_MCP_JAR:-}" ]]; then
  nohup sh -c "tail -f /dev/null | java -Dquarkus.http.host-enabled=true -Dquarkus.http.host=0.0.0.0 -Dquarkus.http.port=$PORT -Dquarkus.log.level=WARN -jar $CAMEL_MCP_JAR" > mcp-server.log 2>&1 &
else
  nohup sh -c "tail -f /dev/null | camel mcp --http --port=$PORT --log-level=WARN" > mcp-server.log 2>&1 &
fi
export MCP_URL="http://127.0.0.1:$PORT/mcp"
for i in $(seq 1 45); do sleep 2; python3 mcp_client.py > /dev/null 2>&1 && { echo "server up after $((i*2))s at $MCP_URL"; python3 mcp_client.py | tail -1; exit 0; }; done
echo "server did not come up; see mcp-server.log"; tail -20 mcp-server.log; exit 1
