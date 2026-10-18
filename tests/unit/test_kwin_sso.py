"""KWin helper identity and fallback tests; never access a real session bus."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('kwin_helper', ROOT / 'scripts/kwin-sso-helper.py')
kwin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kwin)
UUID = '12345678-1234-4234-8234-123456789abc'
PATH = '/org/freedesktop/NetworkManager/ActiveConnection/42'
OWNER = ':1.42'


def fixture():
    active = SimpleNamespace(get_uuid=lambda: UUID, get_path=lambda: PATH, get_vpn=lambda: True,
                             get_state=lambda: 1,
                             get_connection=lambda: SimpleNamespace(get_setting_vpn=lambda: SimpleNamespace(
                                 get_data_item=lambda _: 'true')))
    client = SimpleNamespace(get_dbus_name_owner=lambda: OWNER, get_active_connections=lambda: [active])
    return active, client


@pytest.mark.parametrize('mode, expected', [
    ('pending', 'pending'), ('connected', 'connected'), ('failed', 'cancelled'),
    ('owner', 'cancelled'), ('uuid', 'cancelled'), ('path', 'cancelled'),
    ('not-vpn', 'cancelled'), ('removed', 'cancelled'), ('replaced', 'cancelled'),
])
def test_activation_identity(mode, expected):
    active, client = fixture()
    if mode == 'connected': active.get_state = lambda: 2
    if mode == 'failed': active.get_state = lambda: 4
    if mode == 'owner': client.get_dbus_name_owner = lambda: ':1.99'
    if mode == 'uuid': active.get_uuid = lambda: 'other'
    if mode == 'path': active.get_path = lambda: '/other'
    if mode == 'not-vpn': active.get_vpn = lambda: False
    if mode == 'removed': client.get_active_connections = lambda: []
    if mode == 'replaced': client.get_active_connections = lambda: [SimpleNamespace()]
    assert kwin.activation_phase(client, active, OWNER, UUID, PATH) == expected


@pytest.mark.parametrize('value', ['true', 'false', None, '', 'TRUE', 'invalid', 'no-profile'])
def test_profile_choice_is_explicit(value):
    active, _ = fixture()
    active.get_connection = lambda: None if value == 'no-profile' else SimpleNamespace(
        get_setting_vpn=lambda: SimpleNamespace(get_data_item=lambda _: value))
    assert kwin.profile_closes(active) == (value == 'true')


def test_claim_blocks_retries_and_prunes_finished_activations(tmp_path):
    kwin.claim_activation(tmp_path, OWNER, PATH, [PATH])
    with pytest.raises(FileExistsError):
        kwin.claim_activation(tmp_path, OWNER, PATH, [PATH])
    assert (tmp_path / 'gpclient-sso' / (kwin.activation_key(OWNER, PATH) + '.blocked')).exists()
    other = PATH + '1'
    kwin.claim_activation(tmp_path, OWNER, other, [other])
    assert sorted(item.name for item in (tmp_path / 'gpclient-sso').iterdir()) == [kwin.activation_key(OWNER, other)]


@pytest.mark.parametrize('mode', ['symlink', 'public-directory'])
def test_untrusted_claim_directory_is_rejected(tmp_path, mode):
    if mode == 'symlink':
        target = tmp_path / 'target'; target.mkdir()
        (tmp_path / 'gpclient-sso').symlink_to(target, target_is_directory=True)
    else:
        (tmp_path / 'gpclient-sso').mkdir(mode=0o755)
    with pytest.raises(ValueError):
        kwin.claim_activation(tmp_path, OWNER, PATH, [PATH])
    assert not (tmp_path / 'gpclient-sso' / kwin.activation_key(OWNER, PATH)).exists()


@pytest.mark.parametrize('mode', ['success', 'kwin5', 'no-kwin', 'duplicate', 'startup-failed', 'after-launch-error', 'root', 'foreign-compositor'])
def test_main_fallback_and_cleanup(tmp_path, monkeypatch, mode):
    import sys
    active, client = fixture()
    calls, opened = [], []
    monkeypatch.setattr(kwin.os, 'geteuid', lambda: 0 if mode == 'root' else 1000)
    monkeypatch.setenv('GP_SSO_UUID', UUID)
    monkeypatch.setenv('GP_SSO_ACTIVE_PATH', PATH)
    monkeypatch.setenv('GP_SSO_NM_OWNER', OWNER)
    monkeypatch.setenv('GP_SSO_ATTEMPT', 'b' * 32)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    class Variant:
        def __init__(self, _signature, value): self.value = value
        def unpack(self): return self.value
    class Invocation:
        def return_value(self, value): pass
        def return_dbus_error(self, *_): calls.append(('rejected', '', 'foreign-sender'))
    class Bus:
        handler = None
        def call_sync(self, destination, path, interface, method, parameters, *_):
            calls.append((destination, path, method))
            if method == 'GetNameOwner' and mode == 'no-kwin': raise RuntimeError('absent')
            if method == 'run':
                if mode == 'kwin5' and path.startswith('/Scripting/Script'): raise RuntimeError('old path')
                self.handler(None, ':1.99' if mode == 'foreign-compositor' else ':1.6', None, None, 'Ready', Variant('()', ()), Invocation())
            return Variant('()', {'GetNameOwner': (':1.6',), 'RequestName': (1,), 'loadScript': (7,),
                                   'run': (), 'unloadScript': (True,), 'Cancel': (), 'ReleaseName': (1,)}[method])
        def register_object(self, _path, _info, handler, *_): self.handler = handler; return 42
        def unregister_object(self, token): assert token == 42; calls.append(('cleanup', '', 'unregister'))
    bus = Bus()
    gio = SimpleNamespace(bus_get_sync=lambda *_: bus, BusType=SimpleNamespace(SESSION=0),
                          DBusCallFlags=SimpleNamespace(NO_AUTO_START=1),
                          DBusNodeInfo=SimpleNamespace(new_for_xml=lambda _: SimpleNamespace(interfaces=[object()])))
    glib = SimpleNamespace(Variant=Variant, VariantType=SimpleNamespace(new=lambda value: value),
                           MainContext=SimpleNamespace(default=lambda: SimpleNamespace(pending=lambda: False)))
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(Gio=gio, GLib=glib,
                                                                     NM=SimpleNamespace(Client=SimpleNamespace(new=lambda _: client))))
    def claim(*_):
        if mode == 'duplicate': raise FileExistsError()
    monkeypatch.setattr(kwin, 'claim_activation', claim)
    class Server:
        host = '127.0.0.1:12345'; path = '/random'; landing_served = False
        def __init__(self, *_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def handle_request(self):
            if mode == 'after-launch-error': raise RuntimeError('loop failed')
            bus.handler(None, ':1.6', None, None, 'Finished', Variant('(s)', ('dry-run',)), Invocation())
    def launch(command, **_):
        opened.append(command)
        return SimpleNamespace(poll=lambda: 1 if mode == 'startup-failed' else 0)
    monkeypatch.setattr(kwin.subprocess, 'Popen', launch)
    from itertools import count
    monkeypatch.setattr(kwin.time, 'monotonic', count().__next__)
    common = SimpleNamespace(sys=SimpleNamespace(argv=['helper', 'browser', 'URL', 'URL'], stderr=sys.stderr),
                             UUID=lambda value: value, re=__import__('re'), secrets=SimpleNamespace(token_hex=lambda _: 'a' * 48),
                             validate_auth_url=lambda _: None,
                             landing_command=lambda browser, original, landing, flags: [browser, landing], LandingServer=Server)
    result = kwin.main(common)
    assert result == (1 if mode in ('no-kwin', 'duplicate', 'startup-failed', 'root', 'foreign-compositor') else 0)
    assert bool(opened) == (mode not in ('no-kwin', 'duplicate', 'root', 'foreign-compositor'))
    if opened:
        assert opened == [['browser', 'http://127.0.0.1:12345/random']]
        assert any(method == 'unloadScript' for _, _, method in calls)
        assert any(method == 'unregister' for _, _, method in calls)
        assert not list(tmp_path.glob('gpclient-sso-*'))
    if mode == 'duplicate': assert any(method == 'Cancel' for _, _, method in calls)
    if mode == 'kwin5': assert any(path == '/7' for _, path, method in calls if method == 'run')
    if mode == 'foreign-compositor': assert any(method == 'foreign-sender' for _, _, method in calls)
