# SSO window tracking design

## Shared activation identity

Before starting authentication the root VPN service snapshots exactly one
activating NetworkManager VPN by UUID, active object path and unique D-Bus owner.
It generates an attempt nonce. The wrapper passes these values explicitly through
the numeric-UID privilege drop; the browser and adapters never run as root.
The upstream submodule is unchanged. Its AuthLauncher inherits these values at
version 2.6.5 (`9e4f459`). Ambiguous or unavailable identity leaves ordinary login
and manual closing available.

The session-user bridge accepts only gpauth's single-use IPv4 loopback UUID URL,
without credentials, query or fragment. It substitutes one URL argument in the
existing browser command, preserving profile/presentation flags. A temporary local
page exposes a random marker in its title; only a new window displaying that
marker is a candidate. The page redirects after recognition or a five-second
fallback, with no-referrer, no-store and restrictive CSP headers. URLs and callback
data are not logged.

## GNOME

`Tracker` stores the exact Meta.Window reference and the exact active connection
object. The extension snapshots the profile's `close-browser` value, watches new
windows and title changes, and compares the browser's Wayland or X11 display to
its Shell session. Success requires the same active object, UUID/path and a
confirmed activated VPN. Expiration, cancellation, object loss, reused windows,
duplicate markers or a second SAML registration invalidate automatic closing.
A normal `Meta.Window.delete` request affects the whole window, never a process.

The GNOME 45-51 entry point uses ES modules. Ubuntu 22.04 builds convert the staged
entry point and shared tracker to GNOME 42-44's legacy loader with
`scripts/build-legacy-extension.py`. No second tracking algorithm is maintained.
The public schemas are compiled for both variants. The former global closing
setting remains only as a deprecated schema key; it is ignored at runtime.

## KWin 5/6

The desktop-user helper binds to the unique owner of `org.kde.KWin` and loads the
packaged script with a random private filename/plugin name. It first waits for
confirmation that the script has captured existing windows and installed its
observers, then launches the marker page. The script supports KWin 5's client
signals/list and KWin 6's window signals/list. It retains the exact target window
reference and rejects existing windows, duplicate markers and lost targets.

KWin asynchronously polls the helper; replies are paced with a GLib timer. The
helper checks the current NetworkManager owner, active object, UUID, path and VPN
state before reporting connection success. Only an explicit true profile value
permits `closeWindow()`. Before closing, the script rechecks all current windows
for ambiguity. All signals are disconnected on completion, and the helper unloads
its script and removes the private temporary script directory on exit.

A per-activation claim under the user's private runtime directory prevents a
second portal/gateway login or a fallback retry from re-enabling closing. The
second registration cancels an existing helper if one is still running. Claims
are pruned after the corresponding active connection disappears. The helper
pins KWin calls to the original unique owner, so a restarted compositor cannot
receive a stale script operation. The adapter does not alter persistent KWin
settings or register global shortcuts.

## Profile and fallback behavior

GTK3, GTK4 and Plasma editors load/save `close-browser=true|false`, unchecked by
default. The GTK forms are wider with vertical scrolling; Plasma advertises a
larger initial/minimum size. The host connection editor still controls the outer
window. The checkbox never changes browser profile data or MIME defaults.

Firefox opens a normal dedicated window with its usual controls; Chromium-family
browsers use app mode. Custom commands that bypass the supplied wrapper retain
manual closing. A read-only-home fallback also retains manual closing. Helper
startup failure retries the original URL; errors after launch never start a
duplicate browser. Failed or cancelled VPN authentication cannot trigger closure.

## Verification

Automated coverage includes profile defaults and true/false round trips in real
GTK editors, helper identity/fallback, generated legacy artifacts, GNOME lifecycle,
KWin 5/6 signals and window identification, cancelled/ambiguous sessions, and
package content checks. Regression tests rejected the previous global setting's
ability to override an unchecked profile before the fix. KWin tests also caught
and fixed a mutable pre-launch snapshot and a non-boolean close value.

Tests using fake buses/windows do not prove live desktop behavior. Earlier live
tests covered GNOME Wayland on Arch 51.1 with Firefox and Ubuntu 26.04 with Firefox
and Chromium. GNOME 42, KWin 5/6, X11 and the new checkbox still need live tests.
Use [the setup guide](gnome-sso-window.md) for that checklist and
[BUILD.md](BUILD.md) for automated checks. Results and remaining limits are in
[FORK_REVIEW.md](FORK_REVIEW.md).
