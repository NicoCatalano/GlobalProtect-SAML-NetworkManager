# Arch build and deployment

Run commands from the project root. Use `scripts/build-arch.sh` for local builds;
it exports the current source patch, builds the package, and checks the
archive against the service, wrapper, helper and extension in this checkout.
It produces one installable package, with no separate debug package.

## Compatibility

The companion allows GNOME Shell 45-51 on Wayland. GNOME 51.1 with Firefox is
confirmed on Arch Linux; versions 45-50 still require live testing.
The existing runtime checks decline automatic closing outside a matching
Wayland session; metadata alone cannot restrict the display-server type.

For standard Ubuntu LTS desktops, the earliest candidate is 24.04 (GNOME 46).
26.04 (GNOME 50) is also within the allowed range. Ubuntu 22.04 ships GNOME 42,
so its VPN plugin can still be used, but this companion requires a separate
legacy port before it can close windows there. Companion Debian packaging and live Ubuntu
browser/SSO verification are still pending.

## Build

Use a full Git checkout. The local Arch recipe applies the exported working-tree
changes to the pinned upstream base `8758f6a5b933a6c9d5f104b88df03778ee83089f`.
That ancestor must be available to the exporter; source ZIPs and shallow clones
may not contain it. The patch helper indexes verified changes only in makepkg's
disposable source checkout, so refreshes can replace previously added files.
It does not stage changes in the development checkout.

```bash
./scripts/build-arch.sh
```

Build workspaces and new packages are under `build/arch/`. Previously built
packages, including the working release 2, are preserved under
`build/arch/previous-packages/`. The bare Git cache at the project root and the
separate `python-sdbus/` AUR checkout are preserved.

## Deploy

Disconnect the VPN first, then:

```bash
sudo systemctl stop nm-gpclient.service
sudo pacman -U "$(cat build/arch/package-path)"
```

Log out of GNOME and log back in. This lets GNOME discover the newly installed
extension and load the installed version.

Then enable the extension and opt into closing:

```bash
gnome-extensions enable gpclient-sso@globalprotect-saml-networkmanager
gsettings --schemadir /usr/share/gnome-shell/extensions/gpclient-sso@globalprotect-saml-networkmanager/schemas set org.gnome.shell.extensions.gpclient-sso close-windows true
```

Connect using the usual GNOME VPN toggle. Closing is requested only after the
matching VPN activates and only for the identified new window. Keep unrelated
tabs out of that window. If no unique window can be identified, close it manually.

The build script records the verified archive in `build/arch/package-path` only
after a successful build and comparison with the current source. A failed build
removes that record, so the install command cannot select a previous build.
Closing defaults to dry run; the explicit setting above enables closing.
The build script never installs a package or changes the running session.

## Disable or roll back

```bash
gnome-extensions disable gpclient-sso@globalprotect-saml-networkmanager
```

To restore the previous working package, disconnect the VPN first:

```bash
sudo pacman -U build/arch/previous-packages/networkmanager-gpclient-git-pr.32.r0.g8758f6a-2-x86_64.pkg.tar.zst
sudo systemctl stop nm-gpclient.service
```

[Implementation, dry-run testing and limitations](gnome-sso-development.md).
