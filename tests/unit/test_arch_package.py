"""Reject an incorrect archive before presenting it as deployable."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("arch_check", ROOT / "scripts/check-arch-package.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.mark.parametrize("state", ["valid", "wrong-version", "stale-wrapper", "missing-schema"])
def test_package_matches_checkout(monkeypatch, state):
    contents = {installed: (ROOT / source).read_bytes() for source, installed in checker.FILES.items()}
    contents[".PKGINFO"] = b"pkgname = networkmanager-gpclient-git\npkgver = test-4\n"
    schema = f"usr/share/gnome-shell/extensions/{checker.EXTENSION}/schemas/gschemas.compiled"
    contents[schema] = b"compiled schema"
    if state == "wrong-version":
        contents[".PKGINFO"] = b"pkgname = networkmanager-gpclient-git\npkgver = test-3\n"
    if state == "stale-wrapper":
        contents["usr/libexec/gpclient/browser-wrapper"] = b"old wrapper"
    if state == "missing-schema":
        contents[schema] = b""
    monkeypatch.setattr(checker.subprocess, "check_output", lambda argv, **kwargs: contents[argv[-1]])
    if state == "valid":
        checker.verify(Path("package.pkg.tar.zst"), "test-4")
    else:
        with pytest.raises(ValueError):
            checker.verify(Path("package.pkg.tar.zst"), "test-4")
