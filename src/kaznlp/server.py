"""Small HTTP service around the cleaning pipeline (``kaznlp serve``).

It uses only the standard library, so the Docker image needs no web framework.
The service is what the CD stage deploys to Kubernetes: other parts of PulseGuard AI
send a raw mention and get back the normalized, PII-masked text.

Endpoints:
    GET  /health  -> {"status": "ok", "version": "..."}   (liveness/readiness probe)
    POST /clean   -> body {"text": "..."} or {"texts": ["...", ...]}
                     answer {"results": [{"normalized", "scrubbed", "pii"}, ...]}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from kaznlp import __version__
from kaznlp.normalize import normalize
from kaznlp.pii import find_pii, scrub

MAX_BODY = 1_000_000  # 1 MB is far more than a batch of social-media posts


def clean_one(text: str) -> dict:
    """Run normalization and PII masking on one text; report which PII kinds were found."""
    normalized = normalize(text)
    return {
        "normalized": normalized,
        "scrubbed": scrub(normalized),
        "pii": sorted({m.kind for m in find_pii(normalized)}),
    }


class Handler(BaseHTTPRequestHandler):
    """Request handler; one instance per request (standard ``http.server`` design)."""

    server_version = f"kaznlp/{__version__}"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (name required by http.server)
        if self.path == "/health":
            self._send(200, {"status": "ok", "version": __version__})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/clean":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send(400, {"error": f"body must be 1..{MAX_BODY} bytes"})
            return
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            texts = data["texts"] if "texts" in data else [data["text"]]
            if not all(isinstance(t, str) for t in texts):
                raise TypeError
        except (ValueError, KeyError, TypeError, AttributeError):
            self._send(400, {"error": 'expected JSON {"text": "..."} or {"texts": [...]}'})
            return
        self._send(200, {"results": [clean_one(t) for t in texts]})


def make_server(host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server; tests use port 0 for a free port."""
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:  # pragma: no cover
    """Start the service and block until Ctrl+C / SIGTERM."""
    httpd = make_server(host, port)
    print(f"kaznlp {__version__} listening on http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
