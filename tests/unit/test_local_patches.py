"""makepkg retains untracked files when refreshing a VCS source checkout."""
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "apply-local-patches.py"


def run(*args, cwd, **kwargs):
    return subprocess.run(args, cwd=cwd, capture_output=True, **kwargs)


@pytest.mark.parametrize("state", ["fresh", "applied", "retained-new", "divergent"])
def test_repeated_patch_preserves_local_files(tmp_path, state):
    run("git", "init", "-q", cwd=tmp_path, check=True)
    original = tmp_path / "original"
    added = tmp_path / "added"
    unrelated = tmp_path / "unrelated"
    original.write_text("before\n")
    unrelated.write_text("keep\n")
    patch = tmp_path / "feature.patch"
    patch.write_text('''diff --git a/original b/original
--- a/original
+++ b/original
@@ -1 +1 @@
-before
+after
diff --git a/added b/added
new file mode 100755
--- /dev/null
+++ b/added
@@ -0,0 +1 @@
+new file
''')
    if state == "applied":
        original.write_text("after\n")
    if state != "fresh":
        added.write_text("different\n" if state == "divergent" else "new file\n")
        added.chmod(0o755)
    result = run("python3", str(HELPER), str(patch), cwd=tmp_path)
    assert unrelated.read_text() == "keep\n"
    if state == "divergent":
        assert result.returncode != 0
        assert original.read_text() == "before\n"
        assert added.read_text() == "different\n"
    else:
        assert result.returncode == 0, result.stderr
        assert original.read_text() == "after\n"
        assert added.read_text() == "new file\n"
        assert added.stat().st_mode & 0o111


def test_makepkg_local_sources_exist_by_basename():
    """makepkg looks up local sources by basename beside PKGBUILD."""
    result = run("bash", "-c", 'source PKGBUILD\nprintf "%s\\0" "${source[@]}"',
                 cwd=ROOT, check=True)
    for entry in result.stdout.decode().rstrip("\0").split("\0"):
        if "://" not in entry:
            assert (ROOT / entry.rsplit("/", 1)[-1]).is_file(), entry


def test_makepkg_refresh_can_apply_updated_generated_files(tmp_path):
    run("git", "init", "-q", cwd=tmp_path, check=True)
    (tmp_path / "base").write_text("base\n")
    run("git", "add", "base", cwd=tmp_path, check=True)
    run("git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "base", cwd=tmp_path, check=True)
    patch = tmp_path / "feature.patch"
    template = '''diff --git a/added b/added
new file mode 100644
--- /dev/null
+++ b/added
@@ -0,0 +1 @@
+{content}
'''
    patch.write_text(template.format(content="first version"))
    run("python3", str(HELPER), str(patch), cwd=tmp_path, check=True)
    run("git", "checkout", "-f", "-B", "makepkg", "HEAD", cwd=tmp_path, check=True)
    patch.write_text(template.format(content="updated version"))
    result = run("python3", str(HELPER), str(patch), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "added").read_text() == "updated version\n"
