# -*- coding: utf-8 -*-
"""Minimal synchronous Model Context Protocol (MCP) client.

The official ``mcp`` SDK requires Python >= 3.10; this project runs on 3.8,
so we speak the wire protocol directly.  Two transports are supported:

* stdio  — spawn the server as a subprocess and exchange newline-delimited
           JSON-RPC 2.0 messages over stdin/stdout (MCP stdio transport);
* SSE    — legacy HTTP+SSE transport: a GET stream delivers an ``endpoint``
           event naming the POST URI, requests are POSTed there and responses
           arrive as ``message`` events on the stream.

Only the subset needed by UrbanAgent is implemented: ``initialize``,
``tools/list`` and ``tools/call``.  Server-initiated requests (``ping``,
``roots/list``) get minimal well-formed answers so long-running servers do
not stall.
"""
import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # SSE servers simply become unavailable
    requests = None

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "urban-agent", "version": "1.0"}


class MCPError(RuntimeError):
    pass


class MCPUnavailable(MCPError):
    """Server could not be started / connected (environment problem)."""


# --------------------------------------------------------------------------
# JSON-RPC endpoint shared by both transports
# --------------------------------------------------------------------------
class _JsonRpcEndpoint:
    def __init__(self) -> None:
        self._next_id = 0
        self._lock = threading.Lock()
        self._pending: Dict[int, "queue.Queue[Dict[str, Any]]"] = {}

    # transport must override -------------------------------------------------
    def _send(self, message: Dict[str, Any]) -> None:
        raise NotImplementedError

    # incoming dispatch (called from reader thread) ---------------------------
    def _fail_pending(self, reason: str) -> None:
        """Transport died: unblock every waiter immediately."""
        with self._lock:
            waiters = list(self._pending.values())
        for q in waiters:
            try:
                q.put_nowait({"error": {"code": -32000, "message": reason}})
            except queue.Full:
                pass

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        if "method" in msg and "id" in msg:            # server -> client request
            self._answer_server_request(msg)
        elif "id" in msg:                              # response to us
            with self._lock:
                q = self._pending.get(msg["id"])
            if q is not None:
                q.put(msg)
        # notifications are ignored

    def _answer_server_request(self, msg: Dict[str, Any]) -> None:
        method = msg.get("method")
        reply: Dict[str, Any] = {"jsonrpc": "2.0", "id": msg["id"]}
        if method == "ping":
            reply["result"] = {}
        elif method == "roots/list":
            reply["result"] = {"roots": []}
        else:
            reply["error"] = {"code": -32601, "message": "method not supported"}
        try:
            self._send(reply)
        except Exception:  # noqa: BLE001 — server may already be gone
            pass

    # outgoing ---------------------------------------------------------------
    def request(self, method: str, params: Optional[Dict[str, Any]] = None,
                timeout: float = 30.0) -> Dict[str, Any]:
        with self._lock:
            self._next_id += 1
            rid = self._next_id
            q: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)
            self._pending[rid] = q
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        try:
            self._send(msg)
            try:
                resp = q.get(timeout=timeout)
            except queue.Empty:
                raise MCPError("%s timed out after %.0fs" % (method, timeout))
        finally:
            with self._lock:
                self._pending.pop(rid, None)
        if "error" in resp:
            err = resp["error"]
            raise MCPError("%s error %s: %s" % (method, err.get("code"), err.get("message")))
        return resp.get("result", {})

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)


# --------------------------------------------------------------------------
# stdio transport
# --------------------------------------------------------------------------
class StdioTransport(_JsonRpcEndpoint):
    def __init__(self, command: str, args: List[str],
                 env: Optional[Dict[str, str]] = None,
                 cwd: Optional[str] = None):
        super().__init__()
        full_env = dict(os.environ)
        full_env.update(env or {})
        try:
            self.proc = subprocess.Popen(
                [command] + list(args), cwd=cwd or None, env=full_env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                errors="replace", bufsize=1)
        except (OSError, ValueError) as err:
            raise MCPUnavailable("cannot spawn %r: %s" % (command, err))
        self._stderr_tail: List[str] = []
        self._write_lock = threading.Lock()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _send(self, message: Dict[str, Any]) -> None:
        if self.proc.poll() is not None:
            raise MCPError("server process exited (rc=%s); stderr tail: %s"
                           % (self.proc.returncode, " | ".join(self._stderr_tail[-5:])))
        data = json.dumps(message, ensure_ascii=False)
        with self._write_lock:
            self.proc.stdin.write(data + "\n")
            self.proc.stdin.flush()

    def _read_stdout(self) -> None:
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # servers sometimes log to stdout — skip non-JSON
            self._dispatch(msg)
        # EOF: server exited — do not leave callers waiting for the timeout
        self._fail_pending("server process exited (rc=%s); stderr tail: %s"
                           % (self.proc.poll(), " | ".join(self._stderr_tail[-5:])))

    def _read_stderr(self) -> None:
        for line in self.proc.stderr:
            self._stderr_tail.append(line.rstrip())
            del self._stderr_tail[:-50]

    def close(self) -> None:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------
# HTTP + SSE transport (legacy MCP remote servers)
# --------------------------------------------------------------------------
class SseTransport(_JsonRpcEndpoint):
    def __init__(self, url: str, connect_timeout: float = 15.0):
        super().__init__()
        if requests is None:
            raise MCPUnavailable("requests not installed; SSE transport unavailable")
        self._base = url
        self._connect_timeout = connect_timeout
        self._endpoint: Optional[str] = None
        self._endpoint_ready = threading.Event()
        self._init_params: Optional[Dict[str, Any]] = None
        self._connect()

    def _connect(self) -> None:
        """(Re)establish the SSE session and wait for its endpoint event."""
        self._endpoint = None
        self._endpoint_ready = threading.Event()
        try:
            self._stream = requests.get(
                self._base, stream=True, timeout=(self._connect_timeout, None),
                headers={"Accept": "text/event-stream"})
            self._stream.raise_for_status()
        except Exception as err:  # noqa: BLE001
            raise MCPUnavailable("cannot connect to %s: %s" % (self._base, err))
        threading.Thread(target=self._read_stream, args=(self._stream,),
                         daemon=True).start()
        if not self._endpoint_ready.wait(self._connect_timeout):
            raise MCPUnavailable("no endpoint event from %s" % self._base)

    def _reconnect(self) -> None:
        try:
            self._stream.close()
        except Exception:  # noqa: BLE001
            pass
        self._connect()
        # replay the MCP handshake so the fresh session accepts tools/call
        if self._init_params is not None:
            super(SseTransport, self).request("initialize", self._init_params,
                                              timeout=30.0)
            self.notify("notifications/initialized")

    def request(self, method: str, params: Optional[Dict[str, Any]] = None,
                timeout: float = 30.0) -> Dict[str, Any]:
        # Some SSE servers expire idle sessions within minutes; a POST to the
        # stale sessionId then fails with 4xx (or the stream just closes).
        # Recover transparently once: new session + handshake replay + retry.
        if method == "initialize":
            self._init_params = params
        try:
            return super().request(method, params, timeout=timeout)
        except MCPError as err:
            msg = str(err)
            # "endpoint not established" = a previous reconnect failed and left
            # the transport dead; it must also trigger a fresh reconnect, or
            # every later call dies instantly for the rest of the batch.
            recoverable = ("-> 4" in msg or "SSE stream closed" in msg
                           or "endpoint not established" in msg)
            if not recoverable or method == "initialize":
                raise
            try:
                self._reconnect()
            except Exception as rerr:  # noqa: BLE001 — server still down:
                # surface a tool-level error now; the NEXT call will retry the
                # reconnect because _endpoint stays unset (recoverable above).
                raise MCPError("reconnect failed: %s" % rerr)
            return super().request(method, params, timeout=timeout)

    def _read_stream(self, stream) -> None:
        # NOTE: not requests.iter_lines — it (a) decodes as Latin-1 when the
        # server omits charset (SSE mandates UTF-8) and (b) uses splitlines(),
        # so mojibake bytes like 0x85 (NEL) shatter long data lines.  We split
        # strictly on \n over the raw byte stream and decode UTF-8 ourselves.
        event, data_lines = "message", []  # SSE defaults
        buf = b""
        try:
            for chunk in stream.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line_b, buf = buf.split(b"\n", 1)
                    raw = line_b.rstrip(b"\r").decode("utf-8", errors="replace")
                    if raw == "":  # event boundary
                        if data_lines:
                            self._on_event(event, "\n".join(data_lines))
                        event, data_lines = "message", []
                    elif raw.startswith("event:"):
                        event = raw[6:].strip()
                    elif raw.startswith("data:"):
                        data_lines.append(raw[5:].lstrip())
        except Exception:  # noqa: BLE001 — connection dropped
            pass
        # Generation guard: after a reconnect this thread belongs to the OLD
        # stream — it must not kill requests pending on the new session.
        if stream is self._stream:
            self._fail_pending("SSE stream closed")

    def _on_event(self, event: str, data: str) -> None:
        if event == "endpoint":
            from urllib.parse import urljoin
            self._endpoint = urljoin(self._base, data.strip())
            self._endpoint_ready.set()
        elif event == "message" and data:
            try:
                self._dispatch(json.loads(data))
            except json.JSONDecodeError:
                pass

    def _send(self, message: Dict[str, Any]) -> None:
        if not self._endpoint:
            raise MCPError("SSE endpoint not established")
        resp = requests.post(self._endpoint, json=message, timeout=30)
        if resp.status_code >= 400:
            raise MCPError("POST %s -> %s" % (self._endpoint, resp.status_code))

    def close(self) -> None:
        try:
            self._stream.close()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# MCP server handle
# --------------------------------------------------------------------------
class MCPServer:
    """One connected MCP server: handshake + tools/list + tools/call."""

    def __init__(self, name: str, transport: _JsonRpcEndpoint,
                 call_timeout: float = 60.0):
        self.name = name
        self.transport = transport
        self.call_timeout = call_timeout
        info = transport.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        }, timeout=30.0)
        self.server_info = info.get("serverInfo", {})
        transport.notify("notifications/initialized")

    def list_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        cursor = None
        while True:
            params: Dict[str, Any] = {"cursor": cursor} if cursor else {}
            result = self.transport.request("tools/list", params, timeout=30.0)
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Returns the raw MCP result: {"content": [...], "isError": bool}."""
        return self.transport.request(
            "tools/call", {"name": tool, "arguments": arguments},
            timeout=self.call_timeout)

    def close(self) -> None:
        self.transport.close()


# --------------------------------------------------------------------------
# config loading (mcp.json, Claude-Desktop style) with Windows translation
# --------------------------------------------------------------------------
def _translate_command(command: str, args: List[str]) -> (str, List[str]):
    """Adapt a Windows-style server spec to the current platform."""
    if sys.platform != "win32" and command.lower() in ("cmd", "cmd.exe"):
        # ["cmd", "/c", "npx", ...] -> ["npx", ...]
        rest = list(args)
        if rest and rest[0].lower() in ("/c", "/k"):
            rest = rest[1:]
        if rest:
            return rest[0], rest[1:]
    return command, list(args)


def connect_servers(config_path: str,
                    exclude: Optional[List[str]] = None,
                    call_timeout: float = 60.0):
    """Connect every server in an mcp.json.

    Returns (servers, failures): ``servers`` is {name: MCPServer} for the ones
    that came up; ``failures`` is {name: reason} for the ones that did not —
    the caller decides whether missing servers are fatal.
    """
    with open(config_path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    entries = spec.get("mcpServers", spec)
    exclude = set(exclude or [])

    servers: Dict[str, MCPServer] = {}
    failures: Dict[str, str] = {}
    for name, entry in entries.items():
        if name in exclude:
            continue
        try:
            url = entry.get("url") or entry.get("serverUrl")
            if url:
                transport = SseTransport(url)
            else:
                command, args = _translate_command(
                    entry["command"], entry.get("args", []))
                transport = StdioTransport(
                    command, args, env=entry.get("env"),
                    cwd=entry.get("workingDirectory"))
            servers[name] = MCPServer(name, transport, call_timeout=call_timeout)
        except (MCPError, KeyError, OSError) as err:
            failures[name] = str(err)
    return servers, failures
