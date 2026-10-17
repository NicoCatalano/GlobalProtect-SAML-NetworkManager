import {Tracker} from '../../extensions/gpclient-sso@globalprotect-saml-networkmanager/tracker.js';

let assertions = 0;
function check(value, message) {
    assertions++;
    if (!value)
        throw new Error(message);
}
const uuid = '12345678-1234-4234-8234-123456789abc';
const path = '/org/freedesktop/NetworkManager/ActiveConnection/42';
const marker = 'a'.repeat(48);
const attempt = 'b'.repeat(32);
function fixture(existing = []) {
    const active = {
        state: 1,
        get_uuid: () => uuid,
        get_path: () => path,
        get_vpn: () => true,
        get_state() { return this.state; },
    };
    const tracker = new Tracker();
    check(tracker.register(uuid, path, attempt, marker, active, existing, 0), 'registration');
    const window = {get_title: () => `GPSSO:${marker} - Mozilla Firefox`};
    const closed = [];
    const update = (connections = [active], windows = [window], now = 1) =>
        tracker.update(connections, windows, now, item => closed.push(item));
    return {active, tracker, window, closed, update};
}
{
    const {active, tracker, window, closed, update} = fixture();
    tracker.observe(window);
    check(tracker.recognized(marker), 'recognized exact marker');
    update();
    check(closed.length === 0, 'pending activation');
    window.get_title = () => 'Callback requires manual click';
    active.state = 2;
    update();
    check(closed.length === 1 && closed[0] === window, 'close exact reference after navigation');
    update();
    check(closed.length === 1, 'complete only once');
}
for (const state of [0, 3, 4]) {
    const {active, tracker, window, closed, update} = fixture();
    tracker.observe(window);
    active.state = state;
    update();
    check(!closed.length, `non-success state ${state}`);
}
for (const mode of ['no-marker', 'existing-window', 'duplicate-marker', 'manual-close',
    'expired', 'different-vpn', 'retry', 'daemon-restart', 'multiple-saml', 'lost-window']) {
    const {active, tracker, window, closed, update} = fixture();
    if (mode !== 'no-marker')
        tracker.observe(window);
    if (mode === 'existing-window') {
        tracker.attempts.get(marker).existing.add(window);
        tracker.observe(window);
    }
    if (mode === 'duplicate-marker')
        tracker.observe({get_title: window.get_title});
    if (mode === 'manual-close')
        tracker.forgetWindow(window);
    if (mode === 'multiple-saml') {
        check(!tracker.register(uuid, path, attempt, 'c'.repeat(48), active, [], 0), 'decline second SAML');
        check(!tracker.recognized(marker), 'invalidate first SAML');
    }
    active.state = 2;
    let connections = [active];
    if (mode === 'different-vpn' || mode === 'retry' || mode === 'daemon-restart')
        connections = [{...active, get_path: () => mode === 'daemon-restart' ? path : '/other'}];
    update(connections, mode === 'lost-window' ? [] : [window], mode === 'expired' ? 301 : 1);
    check(!closed.length, mode);
}
for (const mode of ['already-active', 'wifi', 'uuid', 'path', 'marker', 'attempt', 'missing']) {
    const {active} = fixture();
    const tracker = new Tracker();
    if (mode === 'already-active') active.state = 2;
    if (mode === 'wifi') active.get_vpn = () => false;
    check(!tracker.register(mode === 'uuid' ? 'wrong' : uuid,
        mode === 'path' ? '/wrong' : path,
        mode === 'attempt' ? '' : attempt,
        mode === 'marker' ? '' : marker,
        mode === 'missing' ? null : active, [], 0), `reject ${mode}`);
}
{
    const {active, tracker, window, closed, update} = fixture();
    tracker.observe({get_title: () => 'Unrelated browser window'});
    tracker.observe(window);
    active.state = 2;
    update();
    check(closed[0] === window, 'unrelated new window untouched');
}

{
    const {active, tracker} = fixture();
    // A failed tracked launch falls back to an untracked authentication window.
    // A later gateway SAML must not re-enable closing for this activation.
    tracker.cancel(marker);
    check(!tracker.register(uuid, path, attempt, 'd'.repeat(48), active, [], 1),
        'cancelled registration blocks later SAML for the same activation');
    check(!tracker.recognized(marker), 'cancel removes tracking');
    // Cancellation of an unknown marker must not invalidate a valid attempt.
    const second = fixture();
    second.tracker.cancel('unknown');
    second.tracker.observe(second.window);
    second.active.state = 2;
    second.update();
    check(second.closed.length === 1, 'unknown cancellation leaves valid tracking intact');
}

print(`${assertions} tracker assertions passed`);
