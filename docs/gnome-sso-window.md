# SSO window setup and testing

The optional adapters identify one new login window and request its closure
only after the matching VPN connects. They never kill browser processes.

## Compatibility and validation

| Desktop | Adapter | Packaging |
|---------|---------|-----------|
| GNOME 42-44 | Legacy entry point generated from the shared tracker/runtime | Selected automatically by Ubuntu 22.04 builds |
| GNOME 45-51 | Modern GNOME extension | Other Ubuntu builds and the Arch recipe |
| KDE Plasma 5/6 | Session-user helper and temporary KWin script | Helper included in the Ubuntu core and Arch package |

Adapters handle X11 and Wayland. These are implemented targets, not a claim of
live verification on every desktop. Previous live tests cover GNOME Wayland on
Arch 51.1 with Firefox and Ubuntu 26.04 with Firefox and Chromium. The new
per-profile option, GNOME 42 adapter and KWin adapters require live tests.

The original core VPN, GTK editors and Ubuntu Plasma packages remain supported.
The local Arch recipe packages GTK editors; on Plasma you can configure the VPN
with `nm-connection-editor` or `nmcli` and use the KWin closing adapter. Native
Plasma editor packages are built by the Ubuntu matrix.

## Arch build and install

Run from a full recursive Git checkout:

```bash
./scripts/build-arch.sh
```

The local recipe applies exported changes to upstream commit `8758f6a5`.
That ancestor must be present, so avoid shallow clones. The build refreshes
`optional-sso.patch` and verifies package contents against current source.
Build outputs are under `build/arch/`; the recipe targets `x86_64`.

Disconnect the VPN, then install the verified archive:

```bash
sudo systemctl stop nm-gpclient.service
sudo pacman -U "$(cat build/arch/package-path)"
```

The manifest is written only after successful verification and removed before
a new build. A failed build cannot advertise an older package as current.
If rebuilding changes `optional-sso.patch`, commit it with the source changes.
Keep generated package archives out of Git.

## Ubuntu build and install

Follow [BUILD.md](BUILD.md) to build and install matching core and desktop
packages. The GNOME package includes the extension and compiled schema. Ubuntu
22.04 builds select the GNOME 42 entry point automatically. The core package
includes the KWin adapter and its Python/GI runtime dependencies.

## Enable and test

On GNOME, log out and back in after installation or extension updates, then:

```bash
gnome-extensions enable gpclient-sso@globalprotect-saml-networkmanager
```

On KDE, the packaged helper loads its KWin script for the login and unloads it
afterwards. No separate KWin-script enable command is needed. Reopen the VPN
configuration after upgrading the editor plugins.

The configuration form has **Close login window after VPN connects**. Start with
it unchecked, save, and connect. The dedicated window should remain open after
the VPN connects. Keep your usual browser session open for this test.

Then disconnect, check the option, save, and repeat. Only the identified new
login window should close, after the VPN connects. Do not add unrelated tabs to
that window. The checkbox is also available through `nmcli`:

```bash
nmcli connection modify "My VPN" +vpn.data "close-browser=false"
nmcli connection modify "My VPN" +vpn.data "close-browser=true"
```

Replace `My VPN` with the actual connection name. Repeat with Firefox, Chromium
and the desktop default:

```bash
nmcli connection modify "My VPN" +vpn.data "browser=firefox"
nmcli connection modify "My VPN" +vpn.data "browser=chromium"
nmcli connection modify "My VPN" +vpn.data "browser=default"
```

With **Browser: default**, a standard Firefox or Chromium-family desktop launcher
is resolved as the desktop user and receives the same dedicated-window flags as
an explicit browser selection. Custom launchers, extra desktop-entry options and
unavailable Python/GI use `xdg-open`; an existing window or tab is left open for
manual closing.

The previous global `gsettings ... close-windows` value no longer controls closing.
Select the checkbox after upgrading if you want to keep automatic closing enabled.

Cancel a login and confirm that no existing browser window closes. Also test a
failed connection, a retry, manually closing the login window and separate
portal/gateway authentication. Ambiguous/reused windows and multiple SAML windows
must remain for manual closing. Verify both X11 and Wayland on each new adapter;
check the session with `echo "$XDG_SESSION_TYPE"`.

## Diagnostics

GNOME extension messages:

```bash
gnome-extensions info gpclient-sso@globalprotect-saml-networkmanager
journalctl --user -b --grep=gpclient-sso
```

The KWin helper writes generic status messages to the wrapper log:

```bash
grep gpclient-sso "/tmp/edge-wrapper-$(id -u).log"
sudo journalctl -u nm-gpclient.service -b
```

An unchecked profile can report `would close tracked login window`; checking the
box permits a normal close request after successful activation. Missing logs do
not establish successful tracking. Authentication still works with manual closing
when an adapter, profile or session cannot be verified.

## Disable or roll back

Uncheck the option and save, or set `close-browser=false`. On GNOME you can also
disable the companion:

```bash
gnome-extensions disable gpclient-sso@globalprotect-saml-networkmanager
```

To restore a previous package, disconnect the VPN and install your saved archive
using `pacman -U` on Arch or matching core/desktop `.deb` files with `apt install`
on Ubuntu. Stop `nm-gpclient.service` before the next connection; log out and back
in if extension code changed. The KWin helper does not install persistent scripts
or change your global KWin configuration.

[Technical design](gnome-sso-development.md) · [Review and test results](FORK_REVIEW.md)
