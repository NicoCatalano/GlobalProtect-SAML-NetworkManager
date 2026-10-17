#!/usr/bin/env python3
"""Optional session-user bridge. Failure before launch falls back to the wrapper."""

import html
import json
import os
import re
import secrets
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit
from uuid import UUID

BUS_NAME = "org.gpclient.SsoWindow"
OBJECT_PATH = "/org/gpclient/SsoWindow"


def validate_auth_url(url):
    """Only gpauth's single-use IPv4 loopback URL, without query/credentials."""
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or not parsed.port
            or not re.fullmatch(r"/[0-9a-f-]{36}", parsed.path)):
        raise ValueError("unsupported authentication URL")
    UUID(parsed.path[1:])
    return url


def landing_page(marker, url, nonce):
    # URL is validated before interpolation. The timer still redirects if the
    # helper or extension disappears after the landing page has loaded.
    return f'''<!doctype html><meta charset="utf-8">
<title>GPSSO:{html.escape(marker)}</title>
<p>Opening VPN sign-in...</p>
<script nonce="{nonce}">
const target = {json.dumps(url)};
let done = false;
function proceed() {{
    if (done) return;
    done = true;
    location.replace(target);
}}
setTimeout(proceed, 5000);
async function poll() {{
    try {{
        const result = await fetch(location.pathname + '/ready', {{cache: 'no-store'}});
        if (result.ok && await result.text() === 'ready') proceed();
    }} catch (_) {{}}
    if (!done) setTimeout(poll, 200);
}}
poll();
</script>'''.encode()


class LandingServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, marker, url, recognized):
        super().__init__(("127.0.0.1", 0), LandingHandler)
        self.timeout = 0.5
        self.landing_served = False
        self.marker = marker
        self.url = url
        self.recognized = recognized
        self.nonce = secrets.token_hex(16)
        self.host = f"127.0.0.1:{self.server_port}"
        self.path = "/" + secrets.token_hex(24)


class LandingHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.connection.settimeout(1)
        if self.headers.get("Host") != self.server.host:
            self.send_error(403)
            return
        if self.path == self.server.path:
            body = landing_page(self.server.marker, self.server.url, self.server.nonce)
            content_type = "text/html; charset=utf-8"
        elif self.path == self.server.path + "/ready":
            body = b"ready" if self.server.recognized() else b"wait"
            content_type = "text/plain"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         f"default-src 'none'; script-src 'nonce-{self.server.nonce}'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)
        if self.path == self.server.path:
            self.server.landing_served = True

    def handle(self):
        # Also bound clients that connect but never finish their request headers.
        self.connection.settimeout(1)
        super().handle()


def landing_command(browser, original_url, landing_url, flags):
    """Keep the wrapper's profile/presentation flags and replace one URL only."""
    command = [browser]
    replacements = 0
    for flag in flags:
        if flag == original_url:
            command.append(landing_url)
            replacements += 1
        elif flag == "--app=" + original_url:
            command.append("--app=" + landing_url)
            replacements += 1
        else:
            command.append(flag)
    if replacements != 1:
        raise ValueError("missing or ambiguous browser URL")
    return command


def main():
    launched = False
    bus = None
    owner = None
    marker = secrets.token_hex(24)
    try:
        if os.geteuid() == 0 or len(sys.argv) < 4:
            return 1
        browser, url = sys.argv[1:3]
        flags = sys.argv[3:]
        validate_auth_url(url)
        landing_command(browser, url, url, flags)
        session = os.environ.get("WAYLAND_DISPLAY", "")
        if not session:
            return 1
        connection_uuid = str(UUID(os.environ["GP_SSO_UUID"]))
        path = os.environ["GP_SSO_ACTIVE_PATH"]
        attempt = os.environ["GP_SSO_ATTEMPT"]
        nm_owner = os.environ["GP_SSO_NM_OWNER"]
        if not re.fullmatch(r":[0-9]+\.[0-9]+", nm_owner):
            return 1
        if not re.fullmatch(r"/org/freedesktop/NetworkManager/ActiveConnection/[0-9]+", path):
            return 1
        if not re.fullmatch(r"[0-9a-f]{32}", attempt):
            return 1
        # Optional dependency, imported only when correlation is available.
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        owner = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus", "GetNameOwner",
            GLib.Variant("(s)", (BUS_NAME,)), GLib.VariantType.new("(s)"),
            Gio.DBusCallFlags.NO_AUTO_START, 500, None).unpack()[0]

        def call(method, signature, args, reply):
            return bus.call_sync(
                owner, OBJECT_PATH, BUS_NAME, method,
                GLib.Variant(signature, args), GLib.VariantType.new(reply),
                Gio.DBusCallFlags.NO_AUTO_START, 500, None).unpack()

        if not call("Register", "(ssssss)", (connection_uuid, path, attempt, marker, session, nm_owner), "(b)")[0]:
            return 1

        def recognized():
            try:
                return call("Recognized", "(s)", (marker,), "(b)")[0]
            except Exception:
                return True  # Continue login; no replacement extension is used.

        with LandingServer(marker, url, recognized) as server:
            browser_process = subprocess.Popen(landing_command(browser, url, f"http://{server.host}{server.path}", flags),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            launched = True
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                status = browser_process.poll()
                if status not in (None, 0) and not server.landing_served:
                    # Startup failed before loading the marker. Let the wrapper
                    # retry the original URL, and cancel this registration.
                    launched = False
                    return 1
                server.handle_request()
        return 0
    except Exception:
        # Never print exceptions containing authentication URLs or callback data.
        print("gpclient SSO tracking unavailable; manual window closing available", file=sys.stderr)
        return 0 if launched else 1
    finally:
        if not launched and bus is not None and owner is not None:
            try:
                bus.call_sync(owner, OBJECT_PATH, BUS_NAME, "Cancel",
                              GLib.Variant("(s)", (marker,)), None,
                              Gio.DBusCallFlags.NO_AUTO_START, 500, None)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
