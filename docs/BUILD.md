# Build and test

Use a full recursive Git checkout; source ZIPs do not include the VPN backend.
Build as your regular user. Disconnect the VPN before installing or replacing
packages.

```bash
git submodule update --init --recursive
```

## Arch Linux

```bash
./scripts/build-arch.sh
```

This exports patches against a pinned upstream base, builds one package and
compares its installed files with the checkout. Follow the
[Arch installation guide](gnome-sso-window.md#arch-build-and-install).
The recipe currently targets `x86_64` and packages the GTK editors, not Plasma.
It is a local build workflow, not an AUR release.

## Native Ubuntu build

Packaging configurations exist for Ubuntu 22.04, 24.04, 24.10 and 26.04, for
`amd64` and `arm64`. This lists build targets, not a promise that every Ubuntu
release remains maintained. The GNOME companion needs GNOME 45-51 on Wayland;
Ubuntu 22.04's standard desktop can use the VPN but cannot run the companion.
Live SSO testing on Ubuntu currently covers 26.04 with Firefox and Chromium.

Select your host's control file, then install the declared build dependencies:

```bash
. /etc/os-release
cp "debian/control.ubuntu${VERSION_ID}" debian/control
sudo apt update
sudo apt install build-essential devscripts equivs git curl ca-certificates
sudo mk-build-deps --install --remove --tool 'apt-get --no-install-recommends -y' debian/control
```

A missing control file means the host does not match one of the build targets.
The normal build also builds the Plasma editor, even if you only install GNOME.
The selected control file chooses Qt5/KF5 or Qt6/KF6 explicitly.

### Rust

The pinned GlobalProtect-openconnect source requires Rust **1.89 or newer**.
The Docker images use 1.89. With rustup installed:

```bash
rustup toolchain install 1.89
rustup override set 1.89
rustc --version
```

If needed, install rustup first:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/gpclient-rustup.sh
sh /tmp/gpclient-rustup.sh -y --default-toolchain 1.89
. "$HOME/.cargo/env"
```

### Build and install

```bash
dpkg-buildpackage -us -uc -b
```

Packages are written to the parent directory. Disconnect the VPN, then install
the core and one desktop package of the same version together:

```bash
sudo systemctl stop nm-gpclient.service
sudo apt install --reinstall ../network-manager-gpclient_*.deb ../network-manager-gpclient-gnome_*.deb
sudo systemctl daemon-reload
```

Use a directory containing only the intended build's packages. For KDE, use
`network-manager-gpclient-plasma` instead of the GNOME package. The GNOME package
includes the optional extension and compiled schema; a separate manual extension
installation is no longer necessary. Log out and back in before
[enabling and testing it](gnome-sso-window.md#enable-and-test).

`debian/control` is a generated local selection. Do not commit it just because
you built on a different Ubuntu version. Local `.deb` files do not belong in Git.

### Ubuntu 22.04

`python3-sdbus` is not provided by the Ubuntu 22.04 archive. The existing package
requires it; installing a Python module alone does not satisfy an APT package
dependency. This guide does not provide a 22.04 dependency package.
This does not enable the GNOME companion on
GNOME 42. For new companion testing use Ubuntu 24.04 or newer with a supported
GNOME Wayland session.

## Docker Ubuntu build

Use the matching `Dockerfile.ubuntu<version>` with Docker available. For example,
for Ubuntu 26.04 on the host's architecture:

```bash
mkdir -p output/ubuntu26.04
chmod a+rwx output/ubuntu26.04
docker build -t gpclient-builder:ubuntu26.04 -f Dockerfile.ubuntu26.04 .
docker run --rm -v "$PWD/output/ubuntu26.04:/output" gpclient-builder:ubuntu26.04 bash -e -c 'cp debian/control.ubuntu26.04 debian/control; dpkg-buildpackage -us -uc -b; cp /build/*.deb /output/'
```

Use 24.04 in the paths, image name and control file for a 24.04 build. Docker
package tests cannot prove live SSO/window behavior on the desktop.

### KDE neon on Ubuntu 24.04


KDE neon is Ubuntu 24.04 with Plasma 6 / KF6 from `https://archive.neon.kde.org/user`
(suite `noble`). The noble archive has no KF6, so `network-manager-gpclient-plasma-6`
is a second build for 24.04, only of the Plasma plugin (no GNOME plugins, no Rust):
`debian/control.ubuntu24.04-neon` (one binary package) with `Dockerfile.ubuntu24.04-neon`,
which sets the repository up with `.github/scripts/neon-repo.sh` (it checks the
fingerprint of the repository key). `debian/rules` recognises such a control file by
its lack of the core package. CI builds it after the main 24.04 build, with the same
version (`~noble1`), for `amd64` only: neon has no `plasma-nm` for `arm64`. The control
file says so (`Architecture: amd64`) and the workflow reads it from there: a variant is built
for the architectures its binary packages list (`any` is all of them). Locally:

```bash
docker build -t gpclient-builder:ubuntu24.04-neon -f Dockerfile.ubuntu24.04-neon .
docker run --rm -v $(pwd)/output:/output gpclient-builder:ubuntu24.04-neon bash -c \
  'cp debian/control.ubuntu24.04-neon debian/control && dpkg-buildpackage -us -uc -b && cp /build/*.deb /output/'
```


## Automated tests

```bash
sudo apt install python3-pytest gjs
python3 -m pytest tests/unit -q
sudo python3 -m pytest tests/unit -q -p no:cacheprovider
gjs -m tests/unit/sso_tracker.mjs
gjs -m tests/unit/sso_extension.mjs
```

Run Python tests as both a regular user and root; each run exercises different
wrapper paths. The full suite uses Debian packaging tools (`dpkg`, `dpkg-deb`,
`dpkg-buildpackage`) and other host tools listed in CI. On Arch these need an
isolated Ubuntu environment for the full packaging tests.
GJS tests use fake windows and connections, not the real Shell.
See [AGENTS.md](../AGENTS.md) for contributor rules and
[the local review](FORK_REVIEW.md) for results and environment limitations.

## Individual components

```bash
make gnome-plugins
make gpclient
make gpauth
```

For Plasma, use `plugins/plasma/build.sh`, with Qt/KF development dependencies
matching the desired major version. Prefer package installation for desktop tests
so systemd units, the service, plugins and helpers stay in sync.
