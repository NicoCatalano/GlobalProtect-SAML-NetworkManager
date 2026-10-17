"""The build entry point must publish a package path only after verification."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("failure", ["none", "export", "build", "verify"])
def test_failed_build_cannot_advertise_previous_package(tmp_path, failure):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/build-arch.sh", scripts / "build-arch.sh")
    (tmp_path / "PKGBUILD").write_text("pkgver=test\npkgrel=4\n")
    output = tmp_path / "build/arch"
    output.mkdir(parents=True)
    (output / "package-path").write_text("old-package.pkg.tar.zst\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    fake_python = tools / "python3"
    fake_python.write_text('''#!/bin/bash
case "$1" in
    scripts/export-sso-patch.py)
        [ "$FAILURE" != export ]
        ;;
    scripts/check-arch-package.py)
        [ "$FAILURE" != verify ]
        ;;
    *) exit 99 ;;
esac
''')
    fake_python.chmod(0o755)
    fake_makepkg = tools / "makepkg"
    fake_makepkg.write_text('''#!/bin/bash
if [ "$1" = --packagelist ]; then
    printf '%s/packages/new-package.pkg.tar.zst\n' "$BUILDDIR"
else
    [ "$FAILURE" != build ]
fi
''')
    fake_makepkg.chmod(0o755)
    result = subprocess.run(["bash", str(scripts / "build-arch.sh")], cwd=tmp_path,
                            env={**os.environ, "PATH": f"{tools}:{os.environ['PATH']}", "FAILURE": failure},
                            capture_output=True, text=True)
    if failure == "none":
        assert result.returncode == 0, result.stderr
        assert (output / "package-path").read_text() == str(output / "packages/new-package.pkg.tar.zst") + "\n"
        assert "sudo pacman -U" in result.stdout
    else:
        assert result.returncode != 0
        assert not (output / "package-path").exists()
        assert "sudo pacman -U" not in result.stdout
