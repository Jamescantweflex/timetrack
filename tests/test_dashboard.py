"""The dashboard must only answer its own page on this machine."""
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TIMETRACK_DATA_DIR"] = tempfile.mkdtemp()
from timetrack import dashboard  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def req(path, headers=None, method="GET", body=None):
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, data=body)
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_normal_requests_work():
    assert req("/")[0] == 200
    code, body = req("/api/day")
    assert code == 200 and "tracked" in json.loads(body)


def test_dns_rebinding_host_is_refused():
    assert req("/api/day", {"Host": "evil.example.com"})[0] == 403
    assert req("/api/day", {"Host": "evil.example.com:%d" % PORT})[0] == 403
    assert req("/api/day", {"Host": "localhost:%d" % PORT})[0] == 200


def test_cross_site_fetch_is_refused():
    assert req("/api/day", {"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert req("/api/day", {"Sec-Fetch-Site": "same-origin"})[0] == 200
    assert req("/api/day", {"Sec-Fetch-Site": "none"})[0] == 200   # typed in the address bar


def test_link_from_another_site_opens_the_page():
    nav = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
    assert req("/", nav)[0] == 200                       # clicked a link on github.com
    assert req("/api/day", {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors"})[0] == 403
    assert req("/api/day", {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "script"})[0] == 403
    payload = json.dumps({"interrupts": {"enabled": True}}).encode()
    assert req("/api/config", {**nav, "Content-Type": "text/plain", "Origin": "https://evil.example.com"},
               "POST", payload)[0] == 403              # cross-site form submit still refused


def test_menubar_and_snooze():
    code, body = req("/api/menubar")
    d = json.loads(body)
    assert code == 200 and {"title", "symbol", "state", "lines", "snoozed"} <= set(d) and not d["snoozed"]
    p = json.dumps({"minutes": 30}).encode()
    assert req("/api/snooze", {"Content-Type": "application/json"}, "POST", p)[0] == 403          # no header
    assert req("/api/snooze", {"Content-Type": "text/plain", "Origin": "https://evil.example.com"}, "POST", p)[0] == 403
    code, body = req("/api/snooze", {"Content-Type": "application/json", "X-TimeTrack": "1"}, "POST", p)
    assert code == 200 and json.loads(body)["snooze_until"] > 0
    assert json.loads(req("/api/menubar")[1])["snoozed"] is True
    req("/api/snooze", {"Content-Type": "application/json", "X-TimeTrack": "1"}, "POST", json.dumps({"minutes": 0}).encode())
    assert json.loads(req("/api/menubar")[1])["snoozed"] is False


def test_config_post_needs_header_and_origin():
    payload = json.dumps({"interrupts": {"enabled": True}}).encode()
    # form-style post from another site: no preflight, no header -> refused
    assert req("/api/config", {"Content-Type": "text/plain", "Origin": "https://evil.example.com"},
               "POST", payload)[0] == 403
    assert req("/api/config", {"Content-Type": "application/json"}, "POST", payload)[0] == 403
    assert req("/api/config", {"Content-Type": "application/json", "X-TimeTrack": "1",
                               "Origin": "https://evil.example.com"}, "POST", payload)[0] == 403
    code, body = req("/api/config", {"Content-Type": "application/json", "X-TimeTrack": "1",
                                     "Origin": f"http://127.0.0.1:{PORT}"}, "POST", payload)
    assert code == 200 and json.loads(body)["ok"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    srv.shutdown()
