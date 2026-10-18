pkgname=networkmanager-gpclient-git
pkgver=pr.32.r0.g8758f6a
pkgrel=6
pkgdesc='GlobalProtect SAML/SSO VPN plugin for NetworkManager'
arch=('x86_64')
url='https://github.com/NicoCatalano/GlobalProtect-SAML-NetworkManager'
license=('custom')
options=('!buildflags' '!debug')
depends=('networkmanager')
depends+=('openconnect')
depends+=('vpnc')
depends+=('python')
depends+=('python-sdbus')
depends+=('glib2')
depends+=('gtk3')
depends+=('gtk4')
depends+=('libnma')
depends+=('libnma-gtk4')
optdepends=('gnome-shell: optional GNOME 45-51 Wayland SSO window tracking'
            'python-gobject: optional SSO window bridge')
makedepends=('git')
makedepends+=('rust')
makedepends+=('clang')
makedepends+=('pkgconf')
makedepends+=('patch')
provides=('networkmanager-gpclient')
conflicts=('networkmanager-gpclient')
backup=('etc/dbus-1/system.d/nm-gpclient.conf')
backup+=('etc/vpnc/connect.d/90-gpclient-routing')
# Pin the working base used to validate the local prototype patches.
source=('git+https://github.com/WMP/GlobalProtect-SAML-NetworkManager.git#commit=8758f6a5b933a6c9d5f104b88df03778ee83089f')
source+=('activation-via-systemd.patch')
source+=('optional-sso.patch')
source+=('apply-local-patches.py')
sha256sums=('SKIP')
sha256sums+=('SKIP')
sha256sums+=('SKIP')
sha256sums+=('SKIP')

pkgver() {
  cd "$srcdir/GlobalProtect-SAML-NetworkManager"
  git describe --long --tags --always | sed 's/^v//;s/\([^-]*-g\)/r\1/;s/-/./g'
}

prepare() {
  cd "$srcdir/GlobalProtect-SAML-NetworkManager"
  git submodule update --init --recursive
  python3 "$srcdir/apply-local-patches.py" \
    "$srcdir/activation-via-systemd.patch" \
    "$srcdir/optional-sso.patch"
}

build() {
  cd "$srcdir/GlobalProtect-SAML-NetworkManager"
  make all
}

package() {
  cd "$srcdir/GlobalProtect-SAML-NetworkManager"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm755 service/nm-gpclient-service.py "$pkgdir/usr/lib/NetworkManager/nm-gpclient-service"
  install -Dm755 scripts/nm-gpclient-systemd-activate "$pkgdir/usr/lib/NetworkManager/nm-gpclient-systemd-activate"
  install -Dm644 plugins/gnome/libnm-vpn-plugin-gpclient.so "$pkgdir/usr/lib/NetworkManager/libnm-vpn-plugin-gpclient.so"
  install -Dm644 plugins/gnome/libnm-vpn-plugin-gpclient-editor.so "$pkgdir/usr/lib/NetworkManager/libnm-vpn-plugin-gpclient-editor.so"
  install -Dm644 plugins/gnome/libnm-gtk4-vpn-plugin-gpclient-editor.so "$pkgdir/usr/lib/NetworkManager/libnm-gtk4-vpn-plugin-gpclient-editor.so"
  install -Dm644 plugins/gnome/nm-gpclient-service.name "$pkgdir/usr/lib/NetworkManager/VPN/nm-gpclient-service.name"
  install -Dm755 scripts/browser-wrapper.sh "$pkgdir/usr/libexec/gpclient/browser-wrapper"
  install -Dm755 scripts/sso-window-helper.py "$pkgdir/usr/libexec/gpclient/sso-window-helper"
  make DESTDIR="$pkgdir" install-sso-extension
  install -Dm644 config/gpclient-callback.desktop "$pkgdir/usr/share/applications/gpclient-callback.desktop"
  install -Dm755 scripts/edge-wrapper.sh "$pkgdir/usr/libexec/gpclient/edge-wrapper"
  install -Dm755 auth-dialog/nm-gpclient-auth-dialog.py "$pkgdir/usr/libexec/nm-gpclient-auth-dialog"
  install -Dm755 gpclient "$pkgdir/usr/bin/gpclient"
  install -Dm755 gpauth "$pkgdir/usr/bin/gpauth"
  install -Dm644 config/org.freedesktop.NetworkManager.gpclient.service "$pkgdir/usr/share/dbus-1/system-services/org.freedesktop.NetworkManager.gpclient.service"
  install -Dm644 config/nm-gpclient.conf "$pkgdir/etc/dbus-1/system.d/nm-gpclient.conf"
  install -Dm644 config/nm-gpclient.service "$pkgdir/usr/lib/systemd/system/nm-gpclient.service"
  install -Dm755 config/90-gpclient-routing "$pkgdir/etc/vpnc/connect.d/90-gpclient-routing"
  ln -s NetworkManager/libnm-vpn-plugin-gpclient-editor.so "$pkgdir/usr/lib/libnm-gpclient-properties"
}
