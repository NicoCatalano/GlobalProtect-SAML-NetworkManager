# Configuration and troubleshooting

For installation and a short introduction, start with the [README](../README.md).
Build instructions are in [BUILD.md](BUILD.md). This reference covers connection
settings, browser behavior, components and diagnostics.

## Connection settings

Everything the editors show lives in the connection's `vpn.data`, so it can
also be set with `nmcli connection modify "My VPN" +vpn.data key=value`:

| Key | Default | Meaning |
|-----|---------|---------|
| `gateway` | (required) | Portal address, or gateway address with `as-gateway=true` |
| `as-gateway` | `false` | The address is a gateway - skip the portal workflow |
| `preferred-gateway` | (empty) | Gateway to use; empty means the portal's first proposal. Falls back to the first proposal when the value is not offered |
| `gateway-list` | (written by the service) | The portal's gateway list, `;`-separated. Read by the editors to fill the drop-down. The whole list after reading it page by page, or a list that fits one page (both need gpclient's `Found N` line); otherwise the stored entries plus the ones seen last time |
| `gateway-list-count` | (written by the service) | gpclient's `Found N gateways in portal config` count when the list was last read completely. It marks `gateway-list` as complete; the list is read again when the portal reports another number, and never without that line |
| `auth-mode` | `saml` | `saml` = browser login, `credentials` = username/password collected upfront |
| `username` | (empty) | Username for portals that ask on the terminal |
| `browser` | `edge` | `edge`, `firefox`, `chrome`, `chromium`, `default`, or a path to your own wrapper ([details](EDGE_WRAPPER.md#alternative-browsers)) |
| `fix-openssl` | `auto` | Legacy TLS renegotiation for portals with an old TLS stack. `auto` retries once when the portal needs it and then stores `true` in the profile; `true` uses it from the start; `false` never does |
| `hip` | `true` | Send the HIP (Host Integrity Protection) report |
| `dns` | (empty) | Override the VPN DNS servers, `;`-separated. Empty uses the servers the gateway pushes |
| `dns-domains` | (empty) | Extra search domains, space-separated, added to the ones the gateway pushes |

The DNS servers and search domains the gateway pushes are reported to
NetworkManager as part of the VPN's IP configuration, so they survive
NetworkManager's own DNS recalculations (they used to be applied only by
vpnc-script and were wiped on the next recalculation - see
[#15](https://github.com/WMP/GlobalProtect-SAML-NetworkManager/issues/15)).
This needs the vpnc hook `/etc/vpnc/connect.d/90-gpclient-routing` that the
package installs.

The password for `auth-mode=credentials` is a secret, not data:
`nmcli connection modify "My VPN" +vpn.secrets password=...`


## Desktop packages

| Package | Purpose |
|---------|---------|
| `network-manager-gpclient` | Core VPN service and client binaries |
| `network-manager-gpclient-gnome` | GTK editors and optional GNOME SSO extension |
| `network-manager-gpclient-plasma` | Editor for the Ubuntu release's Plasma version |
| `network-manager-gpclient-plasma-6` | Plasma 6 editor for KDE neon on Ubuntu 24.04, amd64 only |
| `networkmanager-gpclient-git` | Local Arch package with GTK editors and the SSO extension |

The Ubuntu Plasma package uses Qt5 on 22.04/24.04 and Qt6 on 24.10/26.04.
On KDE neon use the separate `plasma-6` package; it conflicts with the regular
Plasma package. Ubuntu 24.04 with Plasma 6 from other sources is not live tested.

## Browser sessions and login windows

Select a friendly browser name in the connection editor, or use:

```bash
nmcli connection modify "My VPN" +vpn.data "browser=firefox"
nmcli connection modify "My VPN" +vpn.data "browser=chromium"
```

Friendly names use the supplied wrapper and optional SSO tracking bridge.
A direct custom executable or wrapper path can bypass this integration.
Firefox opens a dedicated normal window with its tabs and address bar.
Chromium, Chrome and Edge use app mode when launched by the wrapper.
With a writable home, the wrapper leaves the browser to select its usual profile;
with a read-only home, it falls back to a temporary profile and manual closing.

The optional GNOME extension identifies one new login window and closes it only
after the matching NetworkManager VPN activation succeeds. Closing is disabled
by default. Reused windows, ambiguous identification and portal-plus-gateway
login flows are left for manual closing. Never add unrelated tabs to the
tracked login window. Browser processes are never force-killed by the companion.

Shell metadata allows GNOME 45-51; tracking also requires Wayland. Live tests
cover Arch GNOME 51.1 with Firefox and Ubuntu 26.04 GNOME Wayland with Firefox
and Chromium. Other allowed Shell versions and browsers need live validation.
See the [SSO guide](gnome-sso-window.md) for enabling, testing and disabling it,
and the [design notes](gnome-sso-development.md) for correlation and safety rules.

## Components

```
┌─────────────────────────┐
│   GNOME Settings        │
│   KDE Plasma NM         │
│   nm-connection-editor  │
└───────────┬─────────────┘
            │ Configuration
            ▼
┌─────────────────────────┐
│   NetworkManager        │
└───────────┬─────────────┘
            │ D-Bus
            ▼
┌─────────────────────────┐
│ nm-gpclient-service     │  ← Python VPN Service (systemd)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   gpclient / gpauth     │  ← VPN connection + SAML auth
└─────────────────────────┘
```

## Project Structure

```
├── service/                    # Python VPN service backend
│   └── nm-gpclient-service.py
├── plugins/
│   ├── gnome/                  # GNOME/GTK plugins (C)
│   └── plasma/                 # KDE Plasma plugin (C++/Qt)
├── config/                     # NetworkManager & systemd configuration
├── .github/
│   ├── scripts/                # build-apt-repo.sh (apt repository builder)
│   └── workflows/              # build/release and Pages publishing
├── scripts/                    # Helper scripts (browser-wrapper)
├── external/
│   └── GlobalProtect-openconnect/  # VPN client (submodule)
└── debian/                     # Debian packaging
```


The optional session-user bridge is `scripts/sso-window-helper.py`; the GNOME
companion is under `extensions/gpclient-sso@globalprotect-saml-networkmanager/`.
NetworkManager starts the service through the systemd activation launcher.
The service launches `gpclient`/`gpauth`; the browser runs as the desktop user.

## Troubleshooting

### Connection logs

```bash
sudo journalctl -u nm-gpclient.service -b -f
sudo journalctl -u NetworkManager -b -f
journalctl --user -b --grep=gpclient-sso
```

Remove authentication tokens and personal details before sharing logs.

### Running the service manually

Disconnect the VPN and stop the existing service before starting a debug copy:

```bash
sudo systemctl stop nm-gpclient.service
sudo /usr/lib/NetworkManager/nm-gpclient-service --debug
```

`SdBusRequestNameExistsError` means another instance already owns the D-Bus name.
Normal use needs no manual service start; NetworkManager activates it on demand.

### TLS renegotiation error

For `unsafe legacy renegotiation disabled`, the service normally retries with
`--fix-openssl` and records the successful setting. To control it explicitly:

```bash
nmcli connection modify "My VPN" +vpn.data "fix-openssl=true"
```

The alternatives are `auto` (default) and `false`.

### Two authentication windows

A gateway may require its own login after portal authentication. If your address
is itself a gateway, select **Address is a gateway (skip the portal)**. See
[interactive authentication](INTERACTIVE_AUTH.md#two-browser-windows-for-one-connection).

### Browser launch or window size

```bash
GP_BROWSER=firefox /usr/libexec/gpclient/browser-wrapper "https://example.com"
sudo journalctl -u nm-gpclient.service -b
```

Wrapper logs are in `/tmp/edge-wrapper-<uid>.log`, including for other browsers.
A running browser may reuse its remembered window geometry. The GNOME companion
tracks and closes windows; it does not remove Firefox's toolbar or enforce size.
See [browser integration](EDGE_WRAPPER.md) for wrapper details and KDE window rules.

### Connection editor missing

Try `nm-connection-editor` and confirm the GUI package matches the core version.
GTK libraries and Plasma editor libraries are described in the
[GNOME](GNOME_SETTINGS_INTEGRATION.md) and [Plasma](PLASMA_IMPLEMENTATION.md) guides.

## Development and publishing

- [Build and local tests](BUILD.md)
- [Local review and validation limits](FORK_REVIEW.md)
- [Service implementation](PYTHON_SERVICE.md)
- [Debian packaging](PACKAGING.md)
- [APT publishing and signing](APT_REPO.md)
- [Agent and contributor rules](../AGENTS.md)

The fork's APT repository is not published as of 2026-10-18. PR packages and
source builds are the current installation paths. Generated packages belong in
GitHub release assets, not Git history.
