# GNOME SSO implementation and verification notes

The companion extension defaults to **dry run**. It logs `would close tracked
login window` after the exact VPN activation succeeds and leaves the window open.
The installed VPN and systemd activation are not changed by editing this checkout.
No live authentication, installation or GNOME enablement is performed by the tests.

## Behavior

The service snapshots the unique activating VPN object with the profile UUID
before spawning gpclient. It also pins NetworkManager's unique D-Bus owner, so
a daemon restart before registration cannot reuse a stale object path. It
exports the owner, UUID, object path and a random attempt
identifier. At submodule version 2.6.5 (`9e4f459`), AuthLauncher uses inherited
Command environment and `into_non_root` overrides session/user keys without
clearing other keys. The detached browser wrapper inherits them too. Missing
values cause an ordinary browser launch. No upstream code is modified.

For browsers routed through `browser-wrapper` with a writable normal home,
the session-user helper registers a
fresh marker on the session bus, then launches a loopback landing page using the
wrapper's existing browser arguments. Firefox uses `--new-window`; Chrome,
Chromium and Edge use `--app` for a minimal window. Profile and presentation
arguments are preserved, and only the original authentication URL is replaced.
Chromium-family browsers select their normal profile and release channel rather
than being forced into the stable channel's user-data directory.
The extension rejects a different Wayland display and
snapshots existing windows. It tracks the exact new Meta.Window whose title
contains the marker, even after its title changes. The landing page polls for
recognition and redirects in the same window, with an independent five-second
fallback timer. Login does not require a popup or an extra click.

Only NetworkManager's ACTIVATED state on the captured active object permits a
close request. A successful callback or a gpauth exit does not. On cancellation,
failure, expiry (five minutes), missing/ambiguous windows, a different activation,
or a NetworkManager restart, no window is closed. A second registration for the
same active object invalidates the first: portal plus gateway SAML deliberately
falls back to manual closing. Cancelling a registration also blocks further
tracking for that activation, since the fallback may open an untracked window.
A browser startup error before the landing page is served cancels registration
and retries the original URL. A successful launcher handover is not treated as
a failure. Disabling the extension removes all its timers,
window signals and D-Bus registration. The helper pins the extension's bus owner,
so a restart cannot silently register with a replacement instance.

The helper runs as the desktop user, never root. It serves no files and binds
only an ephemeral IPv4 loopback port. Requests require an exact Host and random
path, with no CORS permissions. Redirects are restricted to gpauth's loopback
UUID URL; authentication URLs and callback data are not logged. Same-user
processes are outside this correlation boundary. The extension does not accept
shell commands or arbitrary window identities.

Closing affects the **whole window**. Do not add unrelated tabs to the login
window. GNOME cannot inspect tabs. Replaced windows are not followed.
Unknown browsers routed through the wrapper receive their ordinary URL argument
and can be tracked only if they create a new window exposing the landing-page marker. Reuse of an existing
window or tab invalidates tracking, preserving manual closing. Read-only-home
fallback profiles and sessions without a matching Wayland display also retain
manual closing. Custom browser commands that the service passes directly to
`gpclient` keep that behavior and bypass this optional integration.
There is no resizing, process killing, incognito mode or separate Firefox
profile. Firefox retains its normal controls; Chromium-family app mode
uses a minimal layout. Existing cookies and manual callback approval remain.

Automated launch tests cover Firefox, Chrome, Chromium, Edge and a custom browser,
including bridge failure and literal profile arguments. These use fake browsers.
Real app-mode navigation, existing-profile reuse and SSO still need to be exercised
on each browser. Other browsers' internal UI cannot be removed by GNOME.

## Build and deployment

Use the single [Arch build and deployment guide](gnome-sso-window.md).
The build command is `./scripts/build-arch.sh`; it refreshes the patches and
verifies the produced archive. Older packages are kept in
`build/arch/previous-packages/`. For first discovery or extension code updates,
log out and back in after installation.

## Dry-run identification on GNOME 51.1

Log out and back in after first installing the extension, then:

```bash
gnome-extensions enable gpclient-sso@globalprotect-saml-networkmanager
gsettings --schemadir /usr/share/gnome-shell/extensions/gpclient-sso@globalprotect-saml-networkmanager/schemas set org.gnome.shell.extensions.gpclient-sso close-windows false
journalctl --user --follow --grep=gpclient-sso
```

`--follow` streams new journal entries; `--grep` filters the extension messages.
Connect using the existing GNOME VPN toggle. Keep the chosen browser open with
its usual profile. Complete the callback manually if requested. Expect a
registration log,
then `would close tracked login window` only after the VPN becomes active.
The window must remain open in dry run. If no registration appears, check:

```bash
gnome-extensions info gpclient-sso@globalprotect-saml-networkmanager
sudo journalctl -u nm-gpclient.service -b
```

`-b` selects the current boot. An unavailable extension, optional dependency or
unverified session/activation deliberately falls back to normal authentication.
Do not infer success from a missing log message. Check the normal working login
flow and callback before changing the setting.

Exercise pending manual callback, cancellation, tunnel failure, another active
VPN, a retry, an unrelated new browser window, manual login-window closure and
extension disable/re-enable. None should close an unrelated window. Portal and
gateway SAML should leave both windows open. These live GNOME/SSO tests are still
required; mock tests cannot establish their results.

## Opt-in closing, after dry-run verification

Only after the dry-run log identifies the expected window on successful VPN
activation, opt in explicitly:

```bash
gsettings --schemadir /usr/share/gnome-shell/extensions/gpclient-sso@globalprotect-saml-networkmanager/schemas set org.gnome.shell.extensions.gpclient-sso close-windows true
```

The extension uses Meta.Window.delete with the current Shell timestamp and never
force-kills a browser. An unresponsive browser may ignore the close request.

## Rollback

Disable only the optional integration at any time:

```bash
gnome-extensions disable gpclient-sso@globalprotect-saml-networkmanager
```

Normal VPN login and manual closing remain available. To restore all installed
code, disconnect the VPN, reinstall the saved working archive and stop the
backend before the next connection:

```bash
sudo pacman -U build/arch/previous-packages/networkmanager-gpclient-git-pr.32.r0.g8758f6a-2-x86_64.pkg.tar.zst
sudo systemctl stop nm-gpclient.service
```

No profile edits, MIME resets or deletion of browser data are needed.

## Local verification

The latest local review and its exact validation limits are recorded in
[FORK_REVIEW.md](FORK_REVIEW.md).

```bash
python3 -m pytest tests/unit -q
gjs -m tests/unit/sso_tracker.mjs
gjs -m tests/unit/sso_extension.mjs
bash -n scripts/browser-wrapper.sh PKGBUILD
make DESTDIR=/tmp/gpclient-sso-stage install-sso-extension
```

The Python suite needs loopback sockets and the repository's Debian packaging
tools for its full packaging tests. Run wrapper tests as both root and non-root
as described in AGENTS.md. GJS tests use fake connections and windows, never the
real Shell. Installing into DESTDIR verifies schema compilation without installing
into the live session. Full Rust/package rebuild and real SSO are separate
checks; do not claim them from these commands alone.

API references: [GNOME extension structure](https://gjs.guide/extensions/development/creating.html),
[NetworkManager active connection](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Connection.Active.html),
[normal window close](https://mutter.gnome.org/meta/method.Window.delete.html).
