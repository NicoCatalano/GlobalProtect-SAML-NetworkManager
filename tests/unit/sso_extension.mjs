// Run Shell lifecycle against fakes. No connection to the live Shell or buses.
import Gio from 'gi://Gio';
import {Tracker} from '../../extensions/gpclient-sso@globalprotect-saml-networkmanager/tracker.js';

const filename = Gio.File.new_for_uri(import.meta.url).get_parent().get_parent().get_parent()
    .get_child('extensions/gpclient-sso@globalprotect-saml-networkmanager/extension.js');
const [, bytes] = filename.load_contents(null);
const source = new TextDecoder().decode(bytes).replace(/^import .*;\n/gm, '')
    .replace('export default class', 'return class');
let assertions = 0;
function check(value, message) {
    assertions++;
    if (!value) throw new Error(message);
}
for (const close of [false, true]) {
    const cleaned = [];
    const messages = [];
    let created;
    let windows = [];
    const active = {
        state: 1,
        get_uuid: () => '12345678-1234-4234-8234-123456789abc',
        get_path: () => '/org/freedesktop/NetworkManager/ActiveConnection/42',
        get_vpn: () => true,
        get_state() { return this.state; },
    };
    const client = {nm_running: true, get_active_connections: () => [active],
        get_dbus_name_owner: () => ':1.42'};
    class Extension {
        getSettings() { return {get_boolean: () => close}; }
    }
    const fakeGio = {
        Cancellable: Gio.Cancellable,
        DBus: {session: null}, BusNameOwnerFlags: {NONE: 0},
        DBusExportedObject: {wrapJSObject(xml, _impl) {
            const info = Gio.DBusNodeInfo.new_for_xml(xml);
            check(info.interfaces[0].methods[0].in_args.length === 6, 'registration IPC signature');
            return {export() {}, unexport() { cleaned.push('export'); }};
        }},
        bus_own_name_on_connection: () => 42,
        bus_unown_name(id) { check(id === 42, 'bus id'); cleaned.push('bus'); },
    };
    const fakeGLib = {
        getenv: () => 'wayland-test',
        get_monotonic_time: () => 0,
        timeout_add_seconds: () => 12,
        Source: {remove(id) { check(id === 12, 'timer id'); cleaned.push('timer'); }},
    };
    const fakeNM = {Client: {
        new_async(_cancel, callback) { callback(null, null); },
        new_finish: () => client,
    }};
    const fakeGlobal = {
        display: {list_all_windows: () => windows, connect(_signal, callback) { created = callback; return 23; },
            disconnect(id) { check(id === 23, 'display id'); cleaned.push('display'); }},
        get_current_time: () => 123,
    };
    const Sso = new Function('Gio', 'GLib', 'NM', 'Extension', 'Tracker', 'global', 'console', source)(
        fakeGio, fakeGLib, fakeNM, Extension, Tracker, fakeGlobal,
        {log: message => messages.push(message)});
    const extension = new Sso();
    extension.enable();
    const args = [active.get_uuid(), active.get_path(), 'b'.repeat(32), 'a'.repeat(48)];
    check(!extension.Register(...args, 'other-session', ':1.42'), 'reject other session');
    check(!extension.Register(...args, 'wayland-test', ':1.99'), 'reject restarted daemon');
    check(extension.Register(...args, 'wayland-test', ':1.42'), 'register');
    const signals = new Map();
    let next = 0;
    let deleted = false;
    const window = {
        get_title: () => `GPSSO:${args[3]}`,
        connect(signal, callback) { signals.set(++next, [signal, callback]); return next; },
        disconnect(id) { signals.delete(id); },
        can_close: () => true,
        delete(timestamp) { check(timestamp === 123, 'close timestamp'); deleted = true; },
    };
    windows = [window];
    created(null, window);
    check(extension.Recognized(args[3]), 'recognition');
    extension._update();
    check(!deleted, 'pending login stays open');
    active.state = 2;
    extension._update();
    check(deleted === close, 'setting controls normal close');
    check(messages.includes('gpclient-sso: would close tracked login window') === !close, 'dry run log');
    check(signals.size === 0, 'completed window signals disconnected');
    extension.disable();
    check(cleaned.length === 4 && new Set(cleaned).size === 4, 'disable resources cleaned');
    check(extension._client === null && extension._tracker === null, 'state released');
}
print(`${assertions} extension lifecycle assertions passed`);
