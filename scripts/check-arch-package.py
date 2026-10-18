#!/usr/bin/env python3
"""Verify that the deployable Arch archive contains this checkout's SSO code."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = "gpclient-sso@globalprotect-saml-networkmanager"
FILES = {
    "scripts/kwin-sso-helper.py": "usr/libexec/gpclient/kwin-sso-helper.py",
    "scripts/kwin-sso.js": "usr/libexec/gpclient/kwin-sso.js",
    "service/nm-gpclient-service.py": "usr/lib/NetworkManager/nm-gpclient-service",
    "scripts/nm-gpclient-systemd-activate": "usr/lib/NetworkManager/nm-gpclient-systemd-activate",
    "plugins/gnome/nm-gpclient-service.name": "usr/lib/NetworkManager/VPN/nm-gpclient-service.name",
    "scripts/browser-wrapper.sh": "usr/libexec/gpclient/browser-wrapper",
    "scripts/sso-window-helper.py": "usr/libexec/gpclient/sso-window-helper",
    "config/gpclient-callback.desktop": "usr/share/applications/gpclient-callback.desktop",
}
for name in ("extension.js", "tracker.js", "metadata.json",
             "schemas/org.gnome.shell.extensions.gpclient-sso.gschema.xml"):
    FILES[f"extensions/{EXTENSION}/{name}"] = f"usr/share/gnome-shell/extensions/{EXTENSION}/{name}"


def verify(package, expected_version):
    def read(name):
        return subprocess.check_output(["bsdtar", "-xOf", str(package), name], stderr=subprocess.PIPE)

    metadata = read(".PKGINFO").decode()
    if ("pkgname = networkmanager-gpclient-git\n" not in metadata or
            f"pkgver = {expected_version}\n" not in metadata):
        raise ValueError("Package identity or version does not match the build recipe")
    for source, installed in FILES.items():
        if read(installed) != (ROOT / source).read_bytes():
            raise ValueError(f"Package contains stale or different code: {installed}")
    for name in ("libnm-vpn-plugin-gpclient-editor.so", "libnm-gtk4-vpn-plugin-gpclient-editor.so"):
        if b"Close login window after VPN connects" not in read("usr/lib/NetworkManager/" + name):
            raise ValueError(f"Package contains an editor without the closing control: {name}")
    if not read(f"usr/share/gnome-shell/extensions/{EXTENSION}/schemas/gschemas.compiled"):
        raise ValueError("Compiled extension schema is missing")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]), sys.argv[2])
    except (ValueError, IndexError, OSError, subprocess.CalledProcessError) as error:
        print(f"Package verification failed: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"Verified deployable package: {sys.argv[1]}")
