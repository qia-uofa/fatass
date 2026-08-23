"""Local server for the Python-project spec survey.

Serves index.html, exposes GET /api/spec to read the current spec state
from ../spec.json, and POST /api/spec to write a submitted spec there.
Standard library only.
"""

import json
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "index.html"
SPEC_PATH = BASE_DIR.parent / "spec.json"


def read_spec() -> dict:
    if not SPEC_PATH.exists():
        return {}
    try:
        with SPEC_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def write_spec(data: dict) -> None:
    with SPEC_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


class Handler(BaseHTTPRequestHandler):
    server_version = "SpecSurvey/1.0"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_file(INDEX_PATH, "text/html; charset=utf-8")
        elif path == "/api/spec":
            self._send_json(HTTPStatus.OK, read_spec())
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/spec":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            return

        if not isinstance(data, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON object"})
            return

        try:
            write_spec(data)
        except OSError as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, {"status": "ok", "spec": data})

    def log_message(self, fmt, *args):  # quieter default logging
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = 8787
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Spec survey running at {url}")
    print(f"Reading/writing spec state at {SPEC_PATH}")

    def _open_browser():
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Timer(0.5, _open_browser).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
