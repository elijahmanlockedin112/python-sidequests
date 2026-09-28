"""Learning mode as a localhost page.

Binds to 127.0.0.1 only: this server runs your sidequest code and git, so nothing
else on the network may reach it. POSTs need a custom header, which a web page
from another site can't send here without a CORS preflight this server never
approves, and the Host header must be localhost (blocks DNS rebinding).
"""
import json
import os
import threading
import traceback
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import Companion, Refused

PAGE = Path(__file__).with_name("web") / "index.html"
FIRST_PORT = 8950
LOCK = threading.Lock()  # one request at a time touches progress.json

GET_ROUTES = {
    "/api/home": lambda c, _: c.home(),
    "/api/brief": lambda c, _: c.brief(),
    "/api/ladder": lambda c, _: c.ladder(),
    "/api/progress": lambda c, _: c.progress(),
    "/api/evidence": lambda c, _: {"files": c.evidence_today()},
}
POST_ROUTES = {
    "/api/onboard": lambda c, b: c.onboard(b.get("week")),
    "/api/course": lambda c, b: c.record_course(b.get("picked", [])),
    "/api/recall": lambda c, _: c.recall(),
    "/api/rate": lambda c, b: c.rate(b.get("key"), b.get("rating")),
    "/api/reveal": lambda c, _: c.reveal(),
    "/api/editor": lambda c, _: c.open_editor(),
    "/api/check": lambda c, _: c.check(),
    "/api/rung": lambda c, b: c.take_rung(b.get("n")),
    "/api/prompt": lambda c, b: {"prompt": c.prompt(b.get("kind"))},
    "/api/own": lambda c, b: c.own_code(bool(b.get("real")), b.get("files", []), b.get("what")),
    "/api/commit": lambda c, _: c.commit(),
    "/api/skip-commit": lambda c, _: c.skip_commit(),
    "/api/tick": lambda c, b: c.tick(b.get("seconds")),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "PythonSidequests"

    def log_message(self, *args):
        pass  # keep the terminal quiet

    def host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def send(self, status, body, kind="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def run(self, route, body):
        with LOCK:
            c = Companion()
            try:
                result = route(c, body)
            except Refused as e:
                return self.send(409, {"refused": str(e)})
            except Exception as e:  # show it on the page instead of dropping the connection
                traceback.print_exc()
                return self.send(500, {"error": f"{type(e).__name__}: {e}"})
            c.save()
        self.send(200, {"data": result, "notes": c.notes})

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {"error": "localhost only"})
        path = urlsplit(self.path).path
        if path == "/":
            return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/ping":
            return self.send(200, {"app": "python-sidequests"})
        if path in GET_ROUTES:
            return self.run(GET_ROUTES[path], {})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        if not self.host_ok() or self.headers.get("X-Sidequests") != "1":
            return self.send(403, {"error": "localhost page only"})
        route = POST_ROUTES.get(urlsplit(self.path).path)
        if not route:
            return self.send(404, {"error": "not found"})
        length = min(int(self.headers.get("Content-Length") or 0), 65536)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "bad json"})
        self.run(route, body if isinstance(body, dict) else {})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, SO_REUSEADDR would let this bind a port another app is already using.
    allow_reuse_address = os.name != "nt"


def already_running(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return json.load(r).get("app") == "python-sidequests"
    except (OSError, ValueError):
        return False


def serve(open_browser=True):
    for port in range(FIRST_PORT, FIRST_PORT + 10):
        url = f"http://localhost:{port}/"
        if already_running(port):
            print(f"Python Sidequests is already running: {url}", flush=True)
            if open_browser:
                webbrowser.open(url)
            return
        try:
            httpd = Server(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"Ports {FIRST_PORT}-{FIRST_PORT + 9} are all busy.")
    print(f"Python Sidequests  ->  {url}", flush=True)
    print("Leave this window open while you use the page. Ctrl+C stops it.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Go write some Python.")
    finally:
        httpd.server_close()
