// Independent of Shell imports so the safety rules can be tested with GJS.
export class Tracker {
    constructor() {
        this.attempts = new Map();
        this.blockedPaths = new Set();
    }

    register(uuid, path, attempt, marker, active, existing, now) {
        if (!/^[0-9a-f-]{36}$/.test(uuid) || !/^[0-9a-f]{32}$/.test(attempt) ||
            !/^[0-9a-f]{48}$/.test(marker) || this.attempts.has(marker) ||
            this.attempts.size >= 16 || this.blockedPaths.has(path) ||
            !this.matches(active, uuid, path) || active.get_state() !== 1)
            return false;
        // Portal and gateway windows: decline closing for the entire activation.
        for (const entry of this.attempts.values()) {
            if (entry.path === path) {
                entry.ambiguous = true;
                this.blockedPaths.add(path);
                return false;
            }
        }
        this.attempts.set(marker, {
            uuid, path, attempt, marker, active, existing: new Set(existing),
            window: null, ambiguous: false, expires: now + 300,
        });
        return true;
    }

    matches(active, uuid, path) {
        return active !== null && active.get_uuid() === uuid &&
            active.get_path() === path && active.get_vpn();
    }

    observe(window) {
        const title = window.get_title() ?? '';
        for (const entry of this.attempts.values()) {
            if (!title.includes(`GPSSO:${entry.marker}`))
                continue;
            if (entry.existing.has(window)) {
                entry.ambiguous = true;
            } else if (entry.window && entry.window !== window) {
                entry.ambiguous = true;
            } else {
                entry.window = window;
            }
        }
    }

    recognized(marker) {
        const entry = this.attempts.get(marker);
        return Boolean(entry?.window && !entry.ambiguous);
    }

    cancel(marker) {
        const entry = this.attempts.get(marker);
        if (entry) {
            this.blockedPaths.add(entry.path);
            this.attempts.delete(marker);
        }
    }

    forgetWindow(window) {
        for (const [marker, entry] of this.attempts) {
            if (entry.window === window) {
                this.blockedPaths.add(entry.path);
                this.attempts.delete(marker);
            }
        }
    }

    update(activeConnections, windows, now, completed) {
        const paths = new Set(activeConnections.map(active => active.get_path()));
        for (const path of this.blockedPaths) {
            if (!paths.has(path))
                this.blockedPaths.delete(path);
        }
        for (const [marker, entry] of this.attempts) {
            // Identity as well as path: a daemon restart invalidates the object.
            const active = activeConnections.find(item => item === entry.active);
            if (now >= entry.expires || !active ||
                !this.matches(active, entry.uuid, entry.path) || ![1, 2].includes(active.get_state())) {
                this.attempts.delete(marker);
                continue;
            }
            if (active.get_state() !== 2)
                continue;
            // Take a final snapshot to catch a second matching window before close.
            if (entry.window) {
                for (const window of windows)
                    this.observe(window);
            }
            this.attempts.delete(marker);
            this.blockedPaths.add(entry.path);
            if (entry.window && !entry.ambiguous && windows.includes(entry.window))
                completed(entry.window, entry);
        }
    }
}
