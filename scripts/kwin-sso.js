// Loaded for one activation by the session-user helper. Parameters are prepended
// as JSON literals, never executable input. KWin 5 and 6 expose different names.
(function () {
    var existing = windows().slice();
    var watched = [];
    var target = null;
    var ambiguous = false;
    var stopped = false;
    function windows() {
        return typeof workspace.windowList === 'function' ? workspace.windowList() : workspace.clientList();
    }
    function request(method, args, callback) {
        callDBus.apply(null, [ssoBus, '/org/gpclient/SsoWindow', 'org.gpclient.SsoWindow.Kwin', method]
            .concat(args || []).concat(callback || function () {}));
    }
    function observe(window) {
        if (String(window.caption || '').indexOf('GPSSO:' + ssoMarker) < 0)
            return;
        if (existing.indexOf(window) >= 0 || (target && target !== window))
            ambiguous = true;
        else
            target = window;
        request('Observed', [Boolean(target && !ambiguous)]);
    }
    function watch(window) {
        if (watched.some(function (entry) { return entry[0] === window; }))
            return;
        if (watched.length >= 128) {
            ambiguous = true;
            request('Observed', [false]);
            return;
        }
        var changed = function () { observe(window); };
        window.captionChanged.connect(changed);
        watched.push([window, changed]);
        observe(window);
    }
    var added = workspace.windowAdded || workspace.clientAdded;
    var removed = workspace.windowRemoved || workspace.clientRemoved;
    function forget(window) {
        if (target === window) {
            ambiguous = true;
            target = null;
            request('Observed', [false]);
        }
        watched = watched.filter(function (entry) {
            if (entry[0] !== window) return true;
            entry[0].captionChanged.disconnect(entry[1]);
            return false;
        });
    }
    function stop(outcome) {
        if (stopped) return;
        stopped = true;
        added.disconnect(watch);
        removed.disconnect(forget);
        watched.forEach(function (entry) { entry[0].captionChanged.disconnect(entry[1]); });
        watched = [];
        request('Finished', [outcome || 'manual']);
    }
    function poll() {
        request('Poll', [], function (reply) {
            if (stopped) return;
            var state;
            try { state = JSON.parse(reply); } catch (_) { stop(); return; }
            if (!state || typeof state.phase !== 'string') { stop(); return; }
            if (state.phase === 'pending') { poll(); return; }
            var outcome = 'manual';
            if (state.phase === 'connected') {
                var current = windows();
                current.forEach(observe);
                if (target && !ambiguous && current.indexOf(target) >= 0) {
                    if (state.close === true && target.closeable) {
                        target.closeWindow();
                        outcome = 'close-requested';
                    } else if (state.close === false) {
                        outcome = 'dry-run';
                    }
                }
            }
            stop(outcome);
        });
    }
    existing.forEach(watch);
    added.connect(watch);
    removed.connect(forget);
    request('Ready', [], poll);
})();
