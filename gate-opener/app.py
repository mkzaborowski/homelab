#!/usr/bin/env python3
"""Garage / gate opener command API.

POST /garage  -> arms the "garage" command for 1.5 seconds
POST /gate    -> arms the "gate" command for 1.5 seconds
GET  /command -> returns the armed command, or "none" once it expires
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TTL_SECONDS = float(os.environ.get("COMMAND_TTL", "1.5"))
CONSUME_ON_READ = os.environ.get("CONSUME_ON_READ", "").lower() in ("1", "true", "yes")
BASE_COMMAND = "none"

_lock = threading.Lock()
_command = None      # str | None
_expires_at = 0.0    # monotonic timestamp


def arm(name):
    global _command, _expires_at
    with _lock:
        _command = name
        _expires_at = time.monotonic() + TTL_SECONDS
    return TTL_SECONDS


def current():
    """Return (command, seconds_remaining), expiring the stored command if stale.

    With CONSUME_ON_READ the command is cleared as soon as it is handed out, so
    exactly one reader acts on it and a slow poller cannot miss the TTL window.
    """
    global _command, _expires_at
    with _lock:
        remaining = _expires_at - time.monotonic()
        if _command is None or remaining <= 0:
            _command = None
            _expires_at = 0.0
            return BASE_COMMAND, 0.0
        command = _command
        if CONSUME_ON_READ:
            _command = None
            _expires_at = 0.0
        return command, round(remaining, 3)


class Handler(BaseHTTPRequestHandler):
    server_version = "gate-opener/1.0"

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path in ("/garage", "/gate"):
            name = self.path.lstrip("/")
            self._json(200, {"command": name, "expires_in": arm(name)})
        else:
            self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/command":
            command, remaining = current()
            self._json(200, {"command": command, "expires_in": remaining})
        elif self.path == "/healthz":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"listening on :{port} (ttl {TTL_SECONDS}s)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
