import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import NM from 'gi://NM';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {Tracker} from './tracker.js';

const BUS_NAME = 'org.gpclient.SsoWindow';
const PATH = '/org/gpclient/SsoWindow';
const XML = `<node><interface name="${BUS_NAME}">
<method name="Register">
<arg type="s" direction="in"/><arg type="s" direction="in"/>
<arg type="s" direction="in"/><arg type="s" direction="in"/>
<arg type="s" direction="in"/><arg type="s" direction="in"/>
<arg type="b" direction="out"/>
</method>
<method name="Recognized"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
<method name="Cancel"><arg type="s" direction="in"/></method>
</interface></node>`;

export default class SsoWindowExtension extends Extension {
    enable() {
        this._tracker = new Tracker();
        this._settings = this.getSettings();
        this._watched = new Map();
        this._cancellable = new Gio.Cancellable();
        const cancellable = this._cancellable;
        // No synchronous system-bus calls in Shell's event loop.
        NM.Client.new_async(cancellable, (_source, result) => {
            if (cancellable.is_cancelled())
                return;
            try {
                this._client = NM.Client.new_finish(result);
            } catch (_) {
                console.log('gpclient-sso: NetworkManager unavailable');
            }
        });
        this._export = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._export.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(
            Gio.DBus.session, BUS_NAME, Gio.BusNameOwnerFlags.NONE, null, null);
        this._created = global.display.connect('window-created', (_display, window) => {
            if (this._tracker.attempts.size)
                this._watch(window);
        });
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._update();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _windows() {
        return global.display.list_all_windows();
    }

    _now() {
        return GLib.get_monotonic_time() / 1000000;
    }

    Register(uuid, path, attempt, marker, session, nmOwner) {
        // A per-user bus may be shared by more than one graphical session.
        // Decline tracking if we cannot prove the browser targets this Shell.
        const shellSession = GLib.getenv('WAYLAND_DISPLAY');
        if (!shellSession || session !== shellSession ||
            !this._client || this._client.get_dbus_name_owner() !== nmOwner)
            return false;
        const active = this._client?.get_active_connections().find(item => item.get_path() === path) ?? null;
        const windows = this._windows();
        const accepted = this._tracker.register(uuid, path, attempt, marker, active, windows, this._now());
        if (accepted) {
            // Watch existing windows too: reuse must invalidate identification.
            for (const window of windows)
                this._watch(window);
            console.log('gpclient-sso: registered activating VPN login');
        }
        return accepted;
    }

    Recognized(marker) {
        return this._tracker.recognized(marker);
    }

    Cancel(marker) {
        this._tracker.cancel(marker);
    }

    _watch(window) {
        if (this._watched.has(window))
            return;
        if (this._watched.size >= 128) {
            // Too many candidates: fail closed, never guess another target.
            for (const entry of this._tracker.attempts.values())
                entry.ambiguous = true;
            return;
        }
        const title = window.connect('notify::title', () => this._tracker.observe(window));
        const unmanaged = window.connect('unmanaged', () => {
            this._tracker.forgetWindow(window);
            this._unwatch(window);
        });
        this._watched.set(window, [title, unmanaged]);
        this._tracker.observe(window);
    }

    _unwatch(window) {
        for (const signal of this._watched.get(window) ?? [])
            window.disconnect(signal);
        this._watched.delete(window);
    }

    _update() {
        const active = this._client?.nm_running ? this._client.get_active_connections() : [];
        this._tracker.update(active, this._windows(), this._now(), window => {
            if (this._settings.get_boolean('close-windows')) {
                if (window.can_close())
                    window.delete(global.get_current_time());
            } else {
                console.log('gpclient-sso: would close tracked login window');
            }
        });
        if (!this._tracker.attempts.size) {
            for (const window of this._watched.keys())
                this._unwatch(window);
        }
    }

    disable() {
        this._cancellable.cancel();
        GLib.Source.remove(this._timer);
        global.display.disconnect(this._created);
        for (const window of this._watched.keys())
            this._unwatch(window);
        this._export.unexport();
        Gio.bus_unown_name(this._owner);
        this._tracker = null;
        this._client = null;
        this._settings = null;
        this._export = null;
        this._cancellable = null;
    }
}
