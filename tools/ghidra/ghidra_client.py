#!/usr/bin/env python3
"""Thin MCP-over-streamable-HTTP client for the pyghidra-mcp servers.

The godzilla-decomp Ghidra targets run as pyghidra-mcp streamable-http servers on
localhost ports 8031-8032 (see tools/ghidra/workspaces.json). They are NOT registered as session
MCP servers, so this client lets agents drive them directly over HTTP without a
session restart.

Usage:
    ghidra_client.py <port> tools
    ghidra_client.py <port> call <tool_name> '<json-args>'
    ghidra_client.py <port> decompile <symbol_or_addr>
    ghidra_client.py <port> find <name>
    ghidra_client.py <port> search <substring>
    ghidra_client.py <port> xrefs <symbol>
    ghidra_client.py <port> list-functions [--limit N]
    ghidra_client.py <port> strings <substring>

Ports: 8031 halo (cachebeta.exe + cachebeta.xbe)   8032 cea (HCEX.xex + HCEX_Release.xex)

Output is the raw tool result JSON (one object) on stdout. Errors -> stderr, exit 1.
"""
import json
import sys
import urllib.request
import urllib.error

PORTS = {
    8031: "halo/cachebeta.exe",
    8032: "cea/HCEX.xex",
}


class MCPClient:
    def __init__(self, port: int, timeout: int = 120):
        self.url = f"http://127.0.0.1:{port}/mcp"
        self.timeout = timeout
        self.session_id = None
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _post(self, payload: dict, expect_body: bool = True):
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")
        # Capture session id from initialize response
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        raw = resp.read().decode(errors="replace")
        if not expect_body:
            return None
        return self._parse_sse(raw)

    @staticmethod
    def _parse_sse(raw: str):
        # Streamable-HTTP returns SSE: lines of "event: ..." / "data: {json}".
        # Collect the last data: payload (the JSON-RPC response).
        result = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload:
                    try:
                        result = json.loads(payload)
                    except json.JSONDecodeError:
                        pass
        if result is None:
            # Some builds answer with plain JSON, not SSE.
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                raise RuntimeError(f"unparseable response: {raw[:500]}")
        return result

    def initialize(self):
        resp = self._post({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ghidra_client", "version": "1"},
            },
        })
        # initialized notification (no id, no body expected)
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_body=False)
        return resp

    def list_tools(self):
        return self._post({"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {}})

    def call(self, name: str, arguments: dict):
        resp = self._post({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        if "error" in resp:
            raise RuntimeError(f"tool error: {json.dumps(resp['error'])[:500]}")
        return resp.get("result", resp)

    def binary_name(self) -> str:
        """Discover the single binary loaded in this project (pyghidra-mcp 1.12.4)."""
        res = _unwrap(self.call("list_project_binaries", {}))
        progs = res.get("programs", []) if isinstance(res, dict) else []
        if not progs:
            raise RuntimeError("no binaries loaded")
        return progs[0]["name"]


def _unwrap(result: dict):
    """tools/call results wrap content in a list of {type:text,text:...}. Flatten."""
    content = result.get("content")
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        joined = "\n".join(texts)
        try:
            return json.loads(joined)
        except (json.JSONDecodeError, TypeError):
            return joined
    return result


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    port = int(sys.argv[1])
    cmd = sys.argv[2]
    args = sys.argv[3:]

    c = MCPClient(port)
    c.initialize()

    if cmd == "tools":
        tools = c.list_tools().get("result", {}).get("tools", [])
        for t in tools:
            print(f"{t['name']}: {t.get('description','').splitlines()[0] if t.get('description') else ''}")
            schema = t.get("inputSchema", {}).get("properties", {})
            if schema:
                print(f"    args: {', '.join(schema.keys())}")
        return

    if cmd == "call":
        name = args[0]
        arguments = json.loads(args[1]) if len(args) > 1 else {}
        print(json.dumps(_unwrap(c.call(name, arguments)), indent=2))
        return

    if cmd == "binary":
        print(c.binary_name())
        return

    # Convenience wrappers over the real pyghidra-mcp 1.12.4 tool surface.
    # Every tool needs binary_name as the first arg; we auto-discover it.
    b = c.binary_name()
    wrappers = {
        "decompile": ("decompile_function",       lambda a: {"binary_name": b, "name_or_address": a[0]}),
        "search":    ("search_functions_by_name", lambda a: {"binary_name": b, "query": a[0], "limit": int(a[1]) if len(a) > 1 else 50}),
        "symbols":   ("search_symbols_by_name",   lambda a: {"binary_name": b, "query": a[0], "limit": int(a[1]) if len(a) > 1 else 50}),
        "xrefs":     ("list_cross_references",    lambda a: {"binary_name": b, "name_or_address": a[0]}),
        "search-code": ("search_code",            lambda a: {"binary_name": b, "query": a[0], "limit": int(a[1]) if len(a) > 1 else 25}),
        "imports":   ("list_imports",             lambda a: {"binary_name": b, "query": a[0] if a else "", "limit": 200}),
        "exports":   ("list_exports",             lambda a: {"binary_name": b, "query": a[0] if a else "", "limit": 200}),
        "strings":   ("search_strings",           lambda a: {"binary_name": b, "query": a[0], "limit": int(a[1]) if len(a) > 1 else 50}),
        "structures": ("list_structures",         lambda a: {"binary_name": b, "query": a[0] if a else "", "limit": 100}),
        "callgraph": ("gen_callgraph",            lambda a: {"binary_name": b, "function_name": a[0]}),
    }
    if cmd in wrappers:
        tool_name, argf = wrappers[cmd]
        print(json.dumps(_unwrap(c.call(tool_name, argf(args))), indent=2))
        return

    print(f"unknown command: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
