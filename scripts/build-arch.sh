#!/bin/bash
# One entry point: refresh local patches, build, and verify the resulting archive.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
export BUILDDIR="$ROOT/build/arch"
export PKGDEST="$BUILDDIR/packages"
export LOGDEST="$BUILDDIR/logs"
mkdir -p "$PKGDEST" "$LOGDEST"
# A failed rebuild must not leave a previous archive advertised as current.
rm -f -- "$BUILDDIR/package-path"
python3 scripts/export-sso-patch.py
makepkg --force --holdver
PACKAGE_LIST=$(makepkg --packagelist)
mapfile -t PACKAGES <<< "$PACKAGE_LIST"
if [ "${#PACKAGES[@]}" -ne 1 ]; then
    echo "Expected exactly one installable package; check PKGBUILD options" >&2
    exit 1
fi
VERSION=$(bash -c 'source PKGBUILD; printf "%s-%s" "$pkgver" "$pkgrel"')
python3 scripts/check-arch-package.py "${PACKAGES[0]}" "$VERSION"
printf '%s\n' "${PACKAGES[0]}" > "$BUILDDIR/package-path"
printf '\nInstall while the VPN is disconnected:\nsudo pacman -U %q\n' "${PACKAGES[0]}"
