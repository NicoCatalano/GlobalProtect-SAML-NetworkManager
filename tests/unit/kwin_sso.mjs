// Exercise the actual per-login KWin script without a compositor or user bus.
import Gio from 'gi://Gio';
const path = Gio.File.new_for_uri(import.meta.url).get_parent().get_parent().get_parent()
    .get_child('scripts/kwin-sso.js');
const [, bytes] = path.load_contents(null);
const source = new TextDecoder().decode(bytes);
let assertions = 0;
function check(value, message) {
    assertions++;
    if (!value) throw new Error(message);
}
function signal() {
    const listeners = new Set();
    return {connect: callback => listeners.add(callback), disconnect: callback => listeners.delete(callback),
        emit(value) { for (const callback of [...listeners]) callback(value); }, size: () => listeners.size};
}
for (const version of [5, 6]) {
for (const mode of ['close', 'dry-run', 'cancel', 'reused', 'duplicate', 'manual-close', 'other-window', 'invalid-reply', 'bad-close-value']) {
    const marker = 'a'.repeat(48);
    const added = signal(), removed = signal();
    function window(caption) {
        return {caption, captionChanged: signal(), closeable: true, closed: 0,
            closeWindow() { this.closed++; }};
    }
    const existing = window('Existing tabs');
    let windows = [existing];
    const workspace = version === 6 ? {windowList: () => windows, windowAdded: added, windowRemoved: removed}
        : {clientList: () => windows, clientAdded: added, clientRemoved: removed};
    const replies = [];
    let recognized = false, finished = false;
    const callDBus = (bus, path, iface, method, ...args) => {
        check(bus === 'org.gpclient.test' && path === '/org/gpclient/SsoWindow', 'fixed RPC destination');
        const callback = args.pop();
        if (method === 'Ready') callback();
        else if (method === 'Poll') replies.push(callback);
        else if (method === 'Observed') recognized = args[0];
        else if (method === 'Finished') finished = true;
    };
    new Function('workspace', 'callDBus', 'ssoBus', 'ssoMarker', source)(workspace, callDBus, 'org.gpclient.test', marker);
    check(replies.length === 1, 'one outstanding poll');
    const login = mode === 'reused' ? existing : window('GPSSO:' + marker);
    if (mode === 'reused') {
        existing.caption = 'GPSSO:' + marker;
        existing.captionChanged.emit();
    } else {
        windows.push(login);
        added.emit(login);
    }
    if (mode === 'duplicate') {
        const second = window('GPSSO:' + marker);
        windows.push(second); added.emit(second);
    }
    if (mode === 'manual-close') {
        windows = windows.filter(item => item !== login); removed.emit(login);
    }
    if (mode === 'other-window') {
        const unrelated = window('Unrelated new window'); windows.push(unrelated); added.emit(unrelated);
    }
    replies.shift()(JSON.stringify({phase: 'pending', close: true}));
    check(!login.closed && !finished, 'pending connection never closes');
    replies.shift()(mode === 'invalid-reply' ? 'broken JSON' : JSON.stringify({
        phase: mode === 'cancel' ? 'cancelled' : 'connected',
        close: mode === 'bad-close-value' ? 'yes' : mode !== 'dry-run',
    }));
    const expected = ['close', 'other-window'].includes(mode);
    check(login.closed === Number(expected), `KWin ${version}: ${mode}`);
    check(!existing.closed, 'existing browser window stays open');
    check(finished, 'completion reported');
    check(!added.size() && !removed.size() && windows.every(item => !item.captionChanged.size()), 'signals cleaned');
}
}
print(`${assertions} KWin adapter assertions passed`);
