"""Fail-safe correlation and landing-server tests, with no user-session access."""
import asyncio
import importlib.util
from pathlib import Path
import subprocess
import threading
import http.client
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sso_helper", ROOT / "scripts/sso-window-helper.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
AUTH_URL = "http://127.0.0.1:42123/12345678-1234-4234-8234-123456789abc"


def test_auth_url():
    assert helper.validate_auth_url(AUTH_URL) == AUTH_URL


@pytest.mark.parametrize("url", [
    "https://example.com/", "http://localhost:80/", "http://127.0.0.2:80/",
    AUTH_URL + "?token=secret", AUTH_URL + "#fragment",
    AUTH_URL.replace("127.0.0.1", "user@127.0.0.1"),
    AUTH_URL.replace(":42123", ""), AUTH_URL.replace("123456789abc", "../../passwd"),
    AUTH_URL.replace(":42123", ":99999"),
])
def test_reject_auth_url(url):
    with pytest.raises(ValueError):
        helper.validate_auth_url(url)


@pytest.mark.parametrize("recognized, expected", [(False, b"wait"), (True, b"ready")])
def test_landing_server(recognized, expected):
    with helper.LandingServer("a" * 48, AUTH_URL, lambda: recognized) as server:
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            def request(path, host=None):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", path, headers={"Host": host or server.host})
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result

            status, headers, body = request(server.path)
            assert status == 200
            assert b"GPSSO:" + b"a" * 48 in body
            assert b"setTimeout(proceed, 5000)" in body
            assert headers["Cache-Control"] == "no-store"
            assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
            assert request(server.path + "/ready")[2] == expected
            assert request(server.path, "attacker.example")[0] == 403
            assert request("/arbitrary-file")[0] == 404
            assert request(server.path + "?url=https://attacker.example")[0] == 404
        finally:
            server.shutdown()
            worker.join()


@pytest.mark.parametrize("states, expected", [
    ([("wanted", True, 1)], "/active/0"),
    ([("other", True, 1)], ""),
    ([("wanted", False, 1)], ""),
    ([("wanted", True, 2)], ""),
    ([("wanted", True, 3)], ""),
    ([("wanted", True, 1), ("wanted", True, 1)], ""),
    ([], ""),
])
def test_service_snapshots_activation(service_module, monkeypatch, states, expected):
    async def result(value):
        return value

    manager = SimpleNamespace(active_connections=result([f"/active/{i}" for i in range(len(states))]))
    connections = {}
    # Lazy awaitables avoid unawaited-coroutine warnings on short circuit paths.
    class Value:
        def __init__(self, value):
            self.value = value
        def __await__(self):
            return result(self.value).__await__()

    for i, (uuid, vpn, state) in enumerate(states):
        connections[f"/active/{i}"] = SimpleNamespace(uuid=Value(uuid), vpn=Value(vpn), state=Value(state))
    daemon = SimpleNamespace(get_name_owner=lambda *_: result(":1.42"))
    monkeypatch.setattr(service_module.BusNameOwner, "new_proxy", lambda *_: daemon, raising=False)
    monkeypatch.setattr(service_module.NMActiveConnections, "new_proxy", lambda *_: manager, raising=False)
    monkeypatch.setattr(service_module.NMActivation, "new_proxy", lambda _, path: connections[path], raising=False)
    assert asyncio.run(service_module.sso_activation_identity("wanted")) == ((expected, ":1.42") if expected else ("", ""))


def test_service_bus_failure_is_optional(service_module, monkeypatch):
    def fail(*_args):
        raise RuntimeError("bus unavailable")
    monkeypatch.setattr(service_module.NMActiveConnections, "new_proxy", fail, raising=False)
    assert asyncio.run(service_module.sso_activation_identity("wanted")) == ("", "")
    assert asyncio.run(service_module.sso_activation_identity("")) == ("", "")


@pytest.mark.parametrize("mode, expected, launched", [
    ("registered", 0, True),
    ("extension-absent", 1, False),
    ("registration-rejected", 1, False),
    ("launch-failed", 1, False),
    ("helper-error-after-launch", 0, True),
    ("missing-correlation", 1, False),
    ("root", 1, False),
    ("browser-exit-failed", 1, True),
    ("browser-handover", 0, True),
    ("browser-exit-after-landing", 0, True),
])
@pytest.mark.parametrize("browser, flags", [
    ("firefox", ["--new-window", AUTH_URL]),
    ("google-chrome", ["--app=" + AUTH_URL, "--profile-directory=Profile 2"]),
    ("chromium", ["--ozone-platform=wayland", "--app=" + AUTH_URL]),
    ("microsoft-edge", ["--app=" + AUTH_URL]),
    ("other-browser", [AUTH_URL]),
])
def test_helper_fallback(monkeypatch, mode, expected, launched, browser, flags):
    import sys
    calls = []
    opened = []
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0 if mode == "root" else 1000)
    monkeypatch.setattr(sys, "argv", ["helper", "/usr/bin/" + browser, AUTH_URL, *flags])
    monkeypatch.setenv("GP_SSO_UUID", "12345678-1234-4234-8234-123456789abc")
    monkeypatch.setenv("GP_SSO_ACTIVE_PATH", "/org/freedesktop/NetworkManager/ActiveConnection/42")
    monkeypatch.setenv("GP_SSO_ATTEMPT", "b" * 32)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test")
    monkeypatch.setenv("GP_SSO_NM_OWNER", ":1.42")
    if mode == "missing-correlation":
        monkeypatch.delenv("GP_SSO_UUID")

    class Bus:
        def call_sync(self, *args):
            method = args[3]
            calls.append(method)
            if mode == "extension-absent":
                raise RuntimeError("no owner")
            return SimpleNamespace(unpack=lambda: {
                "GetNameOwner": (":1.42",),
                "Register": (mode != "registration-rejected",),
                "Cancel": (),
            }[method])

    gio = SimpleNamespace(
        bus_get_sync=lambda *_: Bus(), BusType=SimpleNamespace(SESSION=0),
        DBusCallFlags=SimpleNamespace(NO_AUTO_START=1),
    )
    glib = SimpleNamespace(Variant=lambda *_: None,
                           VariantType=SimpleNamespace(new=lambda value: value))
    monkeypatch.setitem(sys.modules, "gi.repository", SimpleNamespace(Gio=gio, GLib=glib))

    class Server:
        host = "127.0.0.1:12345"
        path = "/random"
        landing_served = mode == "browser-exit-after-landing"
        def __init__(self, *_):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            if mode == "helper-error-after-launch":
                raise RuntimeError("server failure")
        def handle_request(self):
            assert mode in ("browser-exit-failed", "browser-handover", "browser-exit-after-landing")

    def launch(argv, **_kwargs):
        if mode == "launch-failed":
            raise OSError("missing browser")
        opened.append(argv)
        return SimpleNamespace(poll=lambda: 1 if mode in ("browser-exit-failed", "browser-exit-after-landing") else 0)

    ticks = iter([0, 1, 21] if mode in ("browser-exit-failed", "browser-handover", "browser-exit-after-landing") else [0, 21])
    monkeypatch.setattr(helper.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(helper, "LandingServer", Server)
    monkeypatch.setattr(helper.subprocess, "Popen", launch)
    assert helper.main() == expected
    assert bool(opened) == launched
    if launched:
        expected_flags = [flag.replace(AUTH_URL, "http://127.0.0.1:12345/random") for flag in flags]
        assert opened == [["/usr/bin/" + browser, *expected_flags]]
    if mode in ("launch-failed", "browser-exit-failed"):
        assert "Cancel" in calls


@pytest.mark.parametrize("flags", [[], ["https://other.example/"],
    [AUTH_URL, AUTH_URL], ["--app=" + AUTH_URL, AUTH_URL]])
def test_landing_command_rejects_missing_or_ambiguous_url(flags):
    with pytest.raises(ValueError):
        helper.landing_command("browser", AUTH_URL, "http://127.0.0.1:12345/random", flags)


def test_landing_command_keeps_profile_and_literal_arguments():
    flags = ["--profile-directory=Profile 2", "--user-data-dir=/home/session/Profile Data",
             "--app=" + AUTH_URL, "literal;$not-a-command"]
    command = helper.landing_command("/path with spaces/chromium", AUTH_URL,
                                     "http://127.0.0.1:12345/random", flags)
    assert command == ["/path with spaces/chromium", flags[0], flags[1],
                       "--app=http://127.0.0.1:12345/random", flags[3]]
    assert flags[2] == "--app=" + AUTH_URL
