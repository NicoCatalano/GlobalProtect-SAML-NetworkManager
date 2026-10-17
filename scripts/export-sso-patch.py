#!/usr/bin/env python3
"""Refresh the local Arch source patch without staging unrelated local work."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "8758f6a5b933a6c9d5f104b88df03778ee83089f"
TRACKED = ["Makefile", "debian/rules", "service/nm-gpclient-service.py", "scripts/browser-wrapper.sh"]
NEW = ["scripts/sso-window-helper.py", "config/gpclient-callback.desktop"]
NEW += [str(path.relative_to(ROOT)) for path in sorted((ROOT / "extensions/gpclient-sso@globalprotect-saml-networkmanager").rglob("*"))
        if path.is_file() and path.suffix in (".js", ".json", ".xml")]
parts = [subprocess.check_output(["git", "diff", BASE, "--", *TRACKED], cwd=ROOT)]
for name in NEW:
    # --no-index exits 1 for a diff. Any other error must stop the export.
    result = subprocess.run(["git", "diff", "--no-index", "--", "/dev/null", name],
                            cwd=ROOT, capture_output=True)
    if result.returncode != 1:
        raise SystemExit(f"Cannot export {name}")
    parts.append(result.stdout)
(ROOT / "optional-sso.patch").write_bytes(b"".join(parts))
print("Updated optional-sso.patch")
