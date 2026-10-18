# SSO window installation and testing

The optional companion tracks one dedicated browser login window and requests
its closure only after the matching VPN connects. It never kills the browser.
Closing is disabled by default.

## Compatibility and validation

GNOME Shell metadata allows **45-51**; tracking requires **Wayland**. Live testing
covers Arch GNOME 51.1 with Firefox and Ubuntu 26.04 GNOME Wayland with Firefox
and Chromium. Ubuntu tests included cancellation without closing existing windows.
Other allowed GNOME versions and real Chrome/Edge sessions need live validation.

Ubuntu 24.04 is the earliest standard Ubuntu LTS desktop in the companion's
allowed range. Ubuntu 22.04's GNOME 42 cannot run it; the core VPN remains usable.
Legacy GNOME and X11 companion support are outside this fork's scope.

## Arch build and install

Run from a full recursive Git checkout:

```bash
./scripts/build-arch.sh
```

The local recipe applies exported changes to upstream commit `8758f6a5`.
That ancestor must be present, so avoid shallow clones. The build refreshes
`optional-sso.patch` and verifies package contents against current source.
Build outputs are under `build/arch/`; the recipe currently targets `x86_64`.

Disconnect the VPN, then install the verified archive:

```bash
sudo systemctl stop nm-gpclient.service
sudo pacman -U "$(cat build/arch/package-path)"
```

The manifest is written only after successful verification and removed before
a new build. A failed build cannot advertise an older package as current.
The build does not install anything or modify the running session.
If rebuilding changes `optional-sso.patch`, commit the refreshed patch with the
source changes. Keep generated package archives out of Git.

## Ubuntu build and install

Follow [BUILD.md](BUILD.md) to build and install the matching core and GNOME
packages. `network-manager-gpclient-gnome` includes the companion and compiled
schema. A separate `sudo make install-sso-extension` is not needed.

## Enable and test

After installation or extension updates, **log out and back in** so GNOME loads
the installed code. Confirm the desktop session:

```bash
gnome-shell --version
echo "$XDG_SESSION_TYPE"
gnome-extensions enable gpclient-sso@globalprotect-saml-networkmanager
gsettings --schemadir /usr/share/gnome-shell/extensions/gpclient-sso@globalprotect-saml-networkmanager/schemas set org.gnome.shell.extensions.gpclient-sso close-windows false
journalctl --user --follow --grep=gpclient-sso
```

Use the connection editor to select Firefox, then Chromium, or set the friendly
name with `nmcli` (replace `My VPN` with your connection's name):

```bash
nmcli connection modify "My VPN" +vpn.data "browser=firefox"
```

Connect from GNOME while your usual browser session is already open. Complete
authentication. Expect `would close tracked login window` only after the VPN
connects; in this dry run the login window must stay open. Disconnect and repeat:

```bash
nmcli connection modify "My VPN" +vpn.data "browser=chromium"
```

After successful dry runs, enable closing and repeat both browser tests:

```bash
gsettings --schemadir /usr/share/gnome-shell/extensions/gpclient-sso@globalprotect-saml-networkmanager/schemas set org.gnome.shell.extensions.gpclient-sso close-windows true
```

The identified login window should close after connection; other windows must
remain open. Keep unrelated tabs out of the login window. Cancel a login and
check that no existing browser window closes. Also exercise a failed connection,
a retry, manually closing the login window and disabling/re-enabling the extension.
Ambiguous/reused windows and separate portal/gateway logins must be left for
manual closing. A lack of logs does not establish successful tracking.

If tracking fails, inspect:

```bash
gnome-extensions info gpclient-sso@globalprotect-saml-networkmanager
sudo journalctl -u nm-gpclient.service -b
journalctl --user -b --grep=gpclient-sso
```

## Disable or roll back

Disable the optional companion:

```bash
gnome-extensions disable gpclient-sso@globalprotect-saml-networkmanager
```

Ordinary VPN login and manual window closing remain available. To restore a
previous package, disconnect the VPN and install your saved working archive
using `pacman -U` on Arch or matching core/desktop `.deb` files with `apt install`
on Ubuntu. Then stop `nm-gpclient.service` before the next connection, and log
out and back in if the extension code changed.

[Technical design](gnome-sso-development.md) · [Review and test results](FORK_REVIEW.md)
