"""Local dev server: serves the static dashboard and adds POST /api/refresh
to re-fetch Meta data on demand. Not used in production — GitHub Pages only
serves static files, so the refresh button is inert there by design.
"""
import http.server
import json
import os
import socketserver
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from fetch_and_analyze import build_snapshot, write_snapshot  # noqa: E402

load_dotenv()

ROOT = os.path.join(os.path.dirname(__file__), "..")
PORT = int(os.environ.get("PORT", 8000))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_POST(self):
        if self.path != "/api/refresh":
            self.send_error(404)
            return

        token = os.environ.get("ADS_API_TOKEN")
        if not token:
            self._send_json(500, {"ok": False, "error": "ADS_API_TOKEN no está seteado (revisá tu .env)"})
            return

        try:
            snapshot = build_snapshot(token)
            write_snapshot(snapshot)
            self._send_json(200, {"ok": True, "generated_at": snapshot["generated_at"]})
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving on http://localhost:{PORT} (POST /api/refresh re-fetches Meta data)")
        httpd.serve_forever()
