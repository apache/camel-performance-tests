#!/usr/bin/env python3
"""Minimal MCP Streamable HTTP client (protocol 2025-03-26) for camel-jbang-mcp."""
import json, os, urllib.request, itertools


class McpClient:
    def __init__(self, url=os.environ.get("MCP_URL", "http://localhost:9090/mcp")):
        self.url = url
        self.session = None
        self._ids = itertools.count(1)
        self.tools = []

    def _post(self, payload, expect_result=True):
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.session = sid
            ctype = r.headers.get("Content-Type", "")
            body = r.read().decode()
        if not expect_result:
            return None
        if "text/event-stream" in ctype:
            # take the last JSON data: line
            msgs = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
            for m in reversed(msgs):
                try:
                    obj = json.loads(m)
                except json.JSONDecodeError:
                    continue
                if "result" in obj or "error" in obj:
                    return obj
            raise RuntimeError("no JSON-RPC result in SSE body: " + body[:300])
        return json.loads(body) if body.strip() else None

    def initialize(self):
        res = self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": "initialize",
                          "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                     "clientInfo": {"name": "bench", "version": "0"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_result=False)
        return res

    def list_tools(self):
        tools, cursor = [], None
        while True:
            params = {"cursor": cursor} if cursor else {}
            res = self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": "tools/list", "params": params})
            tools.extend(res["result"]["tools"])
            cursor = res["result"].get("nextCursor")
            if not cursor:
                break
        self.tools = tools
        return self.tools

    def call(self, name, arguments):
        res = self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": "tools/call",
                          "params": {"name": name, "arguments": arguments or {}}})
        if "error" in res:
            return "ERROR: " + json.dumps(res["error"])[:2000]
        content = res["result"].get("content", [])
        text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        if res["result"].get("isError"):
            text = "ERROR: " + text
        return text


if __name__ == "__main__":
    c = McpClient()
    print(json.dumps(c.initialize().get("result", {}).get("serverInfo")))
    for t in c.list_tools():
        print(f"{t['name']:45} {t.get('description','')[:110].replace(chr(10),' ')}")
    print("total tools:", len(c.tools))
