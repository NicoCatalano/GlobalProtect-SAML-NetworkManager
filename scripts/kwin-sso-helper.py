#!/usr/bin/env python3
"""Optional KWin 5/6 adapter; all calls and temporary files belong to the user."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

INTERFACE = 'org.gpclient.SsoWindow.Kwin'
OBJECT_PATH = '/org/gpclient/SsoWindow'
XML = '''<node><interface name="org.gpclient.SsoWindow.Kwin">
<method name="Ready"/>
<method name="Observed"><arg type="b" direction="in"/></method>
<method name="Poll"><arg type="s" direction="out"/></method>
<method name="Cancel"/>
<method name="Finished"><arg type="s" direction="in"/></method>
</interface></node>'''


def activation_key(owner, path):
    return hashlib.sha256((owner + '\n' + path).encode()).hexdigest()


def activation_phase(client, active, owner, uuid, path):
    if (client.get_dbus_name_owner() != owner or active not in client.get_active_connections()
            or active.get_uuid() != uuid or active.get_path() != path or not active.get_vpn()):
        return 'cancelled'
    return {1: 'pending', 2: 'connected'}.get(int(active.get_state()), 'cancelled')


def profile_closes(active):
    connection = active.get_connection()
    vpn = connection.get_setting_vpn() if connection else None
    return bool(vpn and vpn.get_data_item('close-browser') == 'true')


def script_source(bus_name, marker):
    return ('var ssoBus = ' + json.dumps(bus_name) + ';\nvar ssoMarker = ' + json.dumps(marker) + ';\n'
            + Path(__file__).with_name('kwin-sso.js').read_text())


def claim_activation(runtime, owner, path, active_paths):
    """Retain a failed/expired attempt until its NM activation disappears."""
    root = Path(runtime)
    if root.is_symlink() or root.stat().st_uid != os.geteuid():
        raise ValueError('untrusted runtime directory')
    directory = root / 'gpclient-sso'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.geteuid() or directory.stat().st_mode & 0o077:
        raise ValueError('untrusted tracking directory')
    live = {activation_key(owner, item) for item in active_paths}
    for item in directory.iterdir():
        name = item.name.removesuffix('.blocked')
        if len(name) == 64 and all(c in '0123456789abcdef' for c in name) and name not in live:
            item.unlink()
    key = activation_key(owner, path)
    claim = directory / key
    try:
        descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        # Persist cancellation even if the first helper has not exported its
        # bus object yet, or has already timed out. Never overwrite a file.
        try:
            blocked = os.open(claim.with_suffix('.blocked'),
                              os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(blocked)
        except FileExistsError:
            pass
        raise
    os.close(descriptor)
    return claim


def main(common):
    launched = False
    bus = None
    registration = None
    script_name = None
    kwin_owner = None
    script_directory = None
    owned_name = None
    state = None
    try:
        from gi.repository import Gio, GLib, NM
        if os.geteuid() == 0:
            return 1
        browser, url = common.sys.argv[1:3]
        flags = common.sys.argv[3:]
        common.validate_auth_url(url)
        common.landing_command(browser, url, url, flags)
        uuid = str(common.UUID(os.environ['GP_SSO_UUID']))
        path = os.environ['GP_SSO_ACTIVE_PATH']
        owner = os.environ['GP_SSO_NM_OWNER']
        if (not common.re.fullmatch(r'/org/freedesktop/NetworkManager/ActiveConnection/[0-9]+', path)
                or not common.re.fullmatch(r':[0-9]+\.[0-9]+', owner)
                or not common.re.fullmatch(r'[0-9a-f]{32}', os.environ['GP_SSO_ATTEMPT'])):
            return 1
        client = NM.Client.new(None)
        active = next((item for item in client.get_active_connections() if item.get_path() == path), None)
        if active is None or activation_phase(client, active, owner, uuid, path) != 'pending':
            return 1
        close = profile_closes(active)
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        def call(destination, object_path, interface, method, signature, args, reply):
            return bus.call_sync(destination, object_path, interface, method,
                                 GLib.Variant(signature, args), GLib.VariantType.new(reply),
                                 Gio.DBusCallFlags.NO_AUTO_START, 1000, None).unpack()

        kwin_owner = call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                          'GetNameOwner', '(s)', ('org.kde.KWin',), '(s)')[0]
        bus_name = INTERFACE + '.a' + activation_key(owner, path)
        try:
            claim = claim_activation(os.environ['XDG_RUNTIME_DIR'], owner, path,
                             [item.get_path() for item in client.get_active_connections()])
        except FileExistsError:
            # A second portal/gateway login invalidates the first, too.
            try:
                call(bus_name, OBJECT_PATH, INTERFACE, 'Cancel', '()', (), '()')
            except Exception:
                pass
            return 1
        if call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                'RequestName', '(su)', (bus_name, 4), '(u)')[0] != 1:
            return 1
        owned_name = bus_name
        state = {'ready': False, 'recognized': False, 'cancelled': False, 'done': False}

        def cancelled():
            return state['cancelled'] or bool(claim and os.path.lexists(claim.with_suffix('.blocked')))

        def method(_connection, sender, _path, _interface, name, parameters, invocation):
            # Only the compositor that loaded this script can acknowledge or
            # poll it. A later login helper may only invalidate the attempt.
            if name != 'Cancel' and sender != kwin_owner:
                invocation.return_dbus_error(INTERFACE + '.UnexpectedSender', 'Unexpected compositor')
                return
            if name == 'Poll':
                def reply():
                    phase = 'cancelled' if cancelled() else activation_phase(client, active, owner, uuid, path)
                    invocation.return_value(GLib.Variant('(s)', (json.dumps({'phase': phase, 'close': close}),)))
                    return GLib.SOURCE_REMOVE
                GLib.timeout_add(250, reply)
                return
            if name == 'Ready':
                state['ready'] = True
            elif name == 'Observed':
                state['recognized'] = parameters.unpack()[0]
            elif name == 'Cancel':
                state['cancelled'] = True
            elif name == 'Finished':
                outcome = parameters.unpack()[0]
                messages = {'dry-run': 'gpclient-sso: would close tracked login window',
                            'close-requested': 'gpclient-sso: requested login window closure'}
                if outcome in messages:
                    print(messages[outcome], file=common.sys.stderr)
                state['done'] = True
            invocation.return_value(GLib.Variant('()', ()))

        info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
        registration = bus.register_object(OBJECT_PATH, info, method, None, None)
        marker = common.secrets.token_hex(24)
        script_name = 'gpclient-sso-' + marker
        script_directory = tempfile.TemporaryDirectory(prefix='gpclient-sso-', dir=os.environ['XDG_RUNTIME_DIR'])
        script = Path(script_directory.name) / 'login.js'
        script.write_text(script_source(bus_name, marker))
        script_id = call(kwin_owner, '/Scripting', 'org.kde.kwin.Scripting', 'loadScript',
                         '(ss)', (str(script), script_name), '(i)')[0]
        if script_id < 0:
            return 1
        # KWin 6 moved script objects; pin every call to the original bus owner.
        for script_path in (f'/Scripting/Script{script_id}', f'/{script_id}'):
            try:
                call(kwin_owner, script_path, 'org.kde.kwin.Script', 'run', '()', (), '()')
                break
            except Exception:
                continue
        else:
            return 1
        context = GLib.MainContext.default()
        deadline = time.monotonic() + 3
        while not state['ready'] and time.monotonic() < deadline:
            while context.pending():
                context.iteration(False)
            time.sleep(0.01)
        if not state['ready'] or state['done'] or cancelled():
            return 1
        with common.LandingServer(marker, url, lambda: state['recognized']) as server:
            server.timeout = 0.1
            process = subprocess.Popen(common.landing_command(browser, url, f'http://{server.host}{server.path}', flags),
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            launched = True
            deadline = time.monotonic() + 300
            while not state['done'] and time.monotonic() < deadline:
                while context.pending():
                    context.iteration(False)
                if process.poll() not in (None, 0) and not server.landing_served:
                    launched = False
                    return 1
                server.handle_request()
        return 0
    except Exception:
        print('gpclient KWin tracking unavailable; manual window closing available', file=common.sys.stderr)
        return 0 if launched else 1
    finally:
        if state is not None:
            state['cancelled'] = True
        if bus is not None:
            if script_name and kwin_owner:
                try:
                    call(kwin_owner, '/Scripting', 'org.kde.kwin.Scripting', 'unloadScript',
                         '(s)', (script_name,), '(b)')
                except Exception:
                    pass
            if registration is not None:
                bus.unregister_object(registration)
            if owned_name:
                try:
                    call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                         'ReleaseName', '(s)', (owned_name,), '(u)')
                except Exception:
                    pass
        if script_directory is not None:
            script_directory.cleanup()
