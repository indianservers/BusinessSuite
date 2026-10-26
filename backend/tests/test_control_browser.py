"""Opt-in browser workflow against the real FastAPI test app and disposable DB.

The HTTP bridge forwards responses unchanged; no API data is mocked.
"""

import os
import json
import subprocess
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from tests.test_suite_access import access_account


@pytest.mark.skipif(
    os.getenv("RUN_CONTROL_BROWSER") != "1", reason="Opt-in real browser workflow"
)
def test_control_center_real_browser(client, db, access_account, superuser_headers):
    class Bridge(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower()
                not in {"host", "content-length", "connection", "accept-encoding"}
            }
            payload = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            response = client.request(
                self.command, self.path, content=payload, headers=headers
            )
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() not in {
                    "content-length",
                    "content-encoding",
                    "transfer-encoding",
                    "connection",
                }:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            try:
                self.wfile.write(response.content)
            except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
                pass  # Browser navigation may cancel an in-flight request.

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = forward

    class QueuedServer(HTTPServer):
        request_queue_size = 128

    server = QueuedServer(("127.0.0.1", 0), Bridge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, CONTROL_BRIDGE=f"http://127.0.0.1:{server.server_port}")
    try:
        process = subprocess.run(
            ["node", str(root / "playwright" / os.environ.get("CONTROL_BROWSER_SCRIPT", "control-live.cjs"))],
            cwd=root / "frontend",
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert process.returncode == 0, process.stdout + process.stderr
        print(process.stdout)
    finally:
        server.shutdown()
        server.server_close()
