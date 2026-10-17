#!/usr/bin/env python3
"""Apply local makepkg patches while retaining identical files from earlier builds."""

from pathlib import Path
import subprocess
import sys


def apply_patch(path):
    patch = Path(path).read_bytes()
    sections = patch.split(b"diff --git ")
    if sections[0].strip() or len(sections) == 1:
        raise ValueError(f"Expected a git-format patch: {path}")
    pending = []
    for section in sections[1:]:
        data = b"diff --git " + section
        forward = subprocess.run(["git", "apply", "--check", "-"],
                                 input=data, capture_output=True)
        if forward.returncode == 0:
            pending.append(data)
            continue
        reverse = subprocess.run(["git", "apply", "--reverse", "--check", "-"],
                                 input=data, capture_output=True)
        if reverse.returncode != 0:
            # Never overwrite divergent untracked files or silently accept a
            # rejected hunk. Validate all sections before changing this patch.
            raise RuntimeError(f"Patch conflicts with build sources: {path}\n"
                               + forward.stderr.decode(errors="replace"))
    for data in pending:
        subprocess.run(["git", "apply", "-"], input=data, check=True)
    # makepkg refreshes this disposable Git checkout between builds. Index the
    # verified paths so its next checkout also removes files added by patches.
    # Otherwise an old, untracked helper survives and blocks its updated patch.
    stats = subprocess.check_output(["git", "apply", "--numstat", "-z", "-"], input=patch)
    paths = [record.split(b"\t", 2)[2] for record in stats.split(b"\0") if record]
    if paths:
        subprocess.run([b"git", b"add", b"--", *paths], check=True)
    print(f"Prepared {Path(path).name}: {len(pending)} file changes applied")


if __name__ == "__main__":
    try:
        for patch_path in sys.argv[1:]:
            apply_patch(patch_path)
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
