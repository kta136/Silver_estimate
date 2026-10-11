"""Loopback stand-in for DDA's public rate endpoints, scripted by each test."""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxy

CURRENT_PATH = "/api/v1/rates/current"
STREAM_PATH = "/sse/rates"
_END = object()


class ScriptedStream:
    """One SSE response; the test decides what is sent and when it ends."""

    def __init__(self, status=200):
        self.status = status
        self.chunks = queue.Queue()

    def send(self, data):
        self.chunks.put(data)

    def send_event(self, event, payload):
        self.send(f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode())

    def close(self):
        self.chunks.put(_END)


class RateServer:
    """Serve scripted current-rates and stream responses on 127.0.0.1."""

    def __init__(self):
        self.requests = []
        self._current = queue.Queue()
        self._streams = queue.Queue()
        self._opened = []
        self._closing = threading.Event()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, args=(0.02,), daemon=True
        )
        self._thread.start()

    @property
    def current_url(self):
        return f"http://127.0.0.1:{self._server.server_port}{CURRENT_PATH}"

    @property
    def stream_url(self):
        return f"http://127.0.0.1:{self._server.server_port}{STREAM_PATH}"

    def paths(self, prefix):
        return [path for path, _headers in self.requests if path.startswith(prefix)]

    def queue_current(self, payload, status=200):
        """Answer the next current-rates request with ``payload``."""
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self._current.put((status, body))

    def queue_stream(self, status=200):
        """Answer the next stream request with a response the test controls."""
        stream = ScriptedStream(status)
        self._streams.put(stream)
        self._opened.append(stream)
        return stream

    def close(self):
        self._closing.set()
        for stream in self._opened:
            stream.close()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5)

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                server.requests.append((self.path, dict(self.headers.items())))
                try:
                    if self.path.startswith(STREAM_PATH):
                        self._serve_stream()
                    else:
                        self._serve_current()
                except OSError:
                    pass  # the client aborted, which several tests do on purpose

            def _serve_current(self):
                # An unscripted request hangs until the test ends, like a dead link.
                while True:
                    try:
                        status, body = server._current.get(timeout=0.02)
                        break
                    except queue.Empty:
                        if server._closing.is_set():
                            return
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _serve_stream(self):
                try:
                    stream = server._streams.get_nowait()
                except queue.Empty:
                    self.send_error(503)
                    return
                self.send_response(stream.status)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.flush()
                while True:
                    chunk = stream.chunks.get()
                    if chunk is _END:
                        return
                    self.wfile.write(chunk)
                    self.wfile.flush()

        return Handler


def direct_manager():
    """A network manager that never routes loopback requests through a proxy."""
    manager = QNetworkAccessManager()
    manager.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
    return manager
