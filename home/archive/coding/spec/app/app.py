#!/usr/bin/env python3
"""Minimal local server for the spec-customization survey.

Serves index.html, exposes a read endpoint for current spec state
(backed by ../spec.json) and a submit endpoint that writes it.
"""

import json
import os
import http.server
import socketserver
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.normpath(os.path.join(HERE, "..", "spec.json"))
INDEX_PATH = os.path.join(HERE, "index.html")
PORT = int(os.environ.get("PORT", "8765"))


def read_spec():
    if os.path.exists(SPEC_PATH):
        try:
            with open(SPEC_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def write_spec(data):
    with open(SPEC_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SpecSurvey/1.0"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._serve_index()
        elif path == "/api/spec":
            self._send_json(200, read_spec())
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/spec":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid JSON"})
                return
            write_spec(data)
            self._send_json(200, {"ok": True})
        else:
            self.send_error(404, "Not found")

    def _serve_index(self):
        try:
            with open(INDEX_PATH, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404, "index.html not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving spec survey at http://127.0.0.1:{PORT}")
        print(f"Reading/writing spec at {SPEC_PATH}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
