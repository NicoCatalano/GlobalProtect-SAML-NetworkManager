# Local fork preparation review

Original review: 2026-10-17. Earlier sections record the scope at that time.
The current expanded scope is in [desktop adapters and profile settings](#desktop-adapters-and-profile-settings-2026-10-18).

## Scope

The review covered the complete staged and unstaged diff against HEAD and the
new extension, helper, Arch packaging tools, tests and documentation. The working
NetworkManager profile, installed package and running extension were not changed.
The upstream `external/` submodule remains at `9e4f459`; no upstream source was
modified. The original development checkout's Git index was preserved.

This section records the original preparation review. PR follow-up and current
validation are recorded below; it is not a release announcement.

## Findings fixed

1. **Registration cancellation allowed later SAML tracking for the same activation.**
   A failed tracked launch may fall back to an untracked login window. Cancelling
   its registration now blocks subsequent registrations for that active object,
   keeping portal/gateway ambiguity on the manual-closing path.
2. **Browser startup errors could strand authentication on the landing page.**
   A non-zero launcher exit before the page is served now cancels registration
   and lets the wrapper retry the original URL. A zero exit, which may represent
   handover to an existing browser, does not trigger a duplicate launch. A page
   that has already loaded is not retried based on launcher exit.
3. **Failed Arch builds left the previous verified package path in place.**
   The build entry point now clears that record before starting. It publishes a
   new path only after building and comparing the archive with current source.
   Deployment instructions use that verified path instead of a hardcoded version.
4. **Updates to files introduced by patches broke repeated makepkg builds.**
   The preparation helper now indexes the verified affected paths in makepkg's
   disposable Git checkout. Its next refresh removes previously added files,
   allowing updated versions to be applied. Divergent, unverified files are
   rejected. This staging does not affect the development checkout's index.

Regression tests reproduced the failures before these fixes. Obsolete browser
process-monitor variables and a trailing blank line in the activation launcher
were also removed. No browser process is killed by the wrapper.

## Publication cleanup

Build workspaces, package archives, the bare source cache and the separate
`python-sdbus/` AUR checkout are ignored. Their existing contents are preserved.
The main deployment guide is `docs/gnome-sso-window.md`; design and verification
notes are in `docs/gnome-sso-development.md`.

The Arch recipe is still a local, pinned-base patch build. The exporter requires
its upstream ancestor to be present in Git history. This is documented and tested;
it is not an AUR publication workflow.

## Verification

- Full non-root unit suite: **2529 passed, 47 skipped**.
- Full root-path suite in a user namespace: **2559 passed, 16 skipped, 1 failed**.
- Final changed Python tests in a root user namespace: **148 passed, 14 skipped**.
- GJS tracker tests: **54 assertions passed**.
- GJS extension lifecycle tests: **29 assertions passed**.
- Arch package release 5: built successfully and verified against current source,
  including the activation launcher, helper, extension and compiled schema.
- An actual repeated makepkg preparation succeeded after the cache fix.
- Shell syntax and the complete working-tree whitespace check passed.

The full suites used official Ubuntu dpkg tools extracted under `/tmp`, exposed
through a temporary user/mount namespace. No host package installation was needed.
The remaining root failure is the existing desktop-session test
`TestSessionEnv.test_finds_a_display_on_this_machine`: the namespace maps the
current UID to 0 while inheriting the desktop's `/run/user/1000` environment.
The same assertion fails against the untouched original source in that environment.
No test was disabled or weakened to hide it. Subsequent native headless Ubuntu
CI passed on commit `3069122`; current-head CI must still pass before merging.

## Platform validation after the Ubuntu work

The user confirmed Arch GNOME 51.1 Wayland with Firefox. The Ubuntu agent recorded
successful Ubuntu 26.04 amd64 package builds and live GNOME Wayland tests with
Firefox and Chromium: authentication succeeded, the dedicated login window closed
after connection, and cancellation preserved existing browser windows. The user
confirmed completion of the Ubuntu build and tests.

Commit `3069122` packages the extension and compiled schema in the Ubuntu GNOME
package. Its PR checks passed for Ubuntu 22.04, 24.04, 24.10 and 26.04 on amd64 and
arm64, all six Python root/non-root jobs, and GJS. This establishes package/test
coverage; it does not establish live GNOME behavior on every build target.
The upgrade workflow falls back to fresh installation while the fork's APT
repository is empty, so green build jobs do not yet prove upgrades from a
published fork release.

Metadata allows GNOME 45-51. Other Shell versions, Chrome, Edge, arm64 desktop
SSO and the remaining failure/ambiguity scenarios require live verification.
Legacy GNOME and X11 companion support are intentionally outside the scope.

## PR follow-up, 2026-10-18

The full PR scope includes systemd activation, the optional GNOME companion,
Arch build tooling and Ubuntu packaging. The README now presents the feature,
screenshots and installation/build paths concisely. Settings, architecture and
diagnostics moved to `docs/TECHNICAL.md`; `docs/README.md` is a documentation index.
Stale references to pending Ubuntu packaging/testing and manual Ubuntu extension
installation were updated.

GitHub Pages is configured, but the public fork APT signing-key URL returned
HTTP 404 on 2026-10-18. APT installation is marked as pending; the guide offers
builds and PR test packages instead. No release, signing key or APT deployment
was created as part of this cleanup.

The exported Arch patch was refreshed to include the Ubuntu changes to Makefile
and Debian rules. The local Arch recipe was advanced to package release 6 and its
project URL now identifies this fork; its upstream source remains deliberately
pinned to the tested base. Build archives stay ignored.

### Out-of-scope finding

The pre-existing `build-all.sh` Docker command ends in `; true`, hiding failed
package builds and potentially presenting old output as a successful rebuild.
The new build guide uses native builds or an explicit `bash -e` Docker command.
A GitHub issue could not be created because this fork has Issues disabled; the
finding is recorded here and in PR #1. A follow-up should propagate errors and
test both successful and failed builds. The multi-release script is unchanged.

### Local follow-up checks

- Arch release 6 built successfully and passed the package content verifier.
- The patched build checkout's Makefile, Debian rules, service and browser wrapper
  match the development checkout byte for byte.
- GJS: 54 tracker assertions and 29 lifecycle assertions passed.
- Extension staging compiled the settings schema successfully.
- Shell syntax checks and source whitespace checks passed. Git-format patch
  context is excluded from whitespace checks because its leading context markers
  necessarily precede Makefile tabs and blank lines.
- Edited Markdown file links and heading anchors resolve locally.

The full root/non-root unit suites and current-head CI are recorded in the PR.
The installed package, running VPN and desktop extension were not changed.

### PR self-review passes

1. Reviewed the incoming PR diff against `origin/main` (`8758f6a`), including
   runtime code, tests, both package paths and docs. Fixed stale patch exports,
   misleading APT installation claims and outdated Ubuntu validation in `39eef8e`.
2. Re-reviewed the complete diff at `39eef8e`. Cross-checking all Ubuntu control
   files found an incorrect new documentation claim about the 22.04 dependency:
   that control file uses `python3-pip`, not `python3-sdbus`. Corrected the build
   guide to describe the separate system-Python module setup and removed the
   inaccurate README prerequisite. No runtime changes were needed.

The final pass and current-head test results are recorded in PR #1.

## Desktop adapters and profile settings, 2026-10-18

The user expanded the scope to automatic closing on Ubuntu 22.04 and KDE Plasma,
a per-VPN checkbox, and a larger configuration form. This supersedes the earlier
legacy/X11 exclusions above.

### Implementation

- GTK3, GTK4 and Plasma editors store explicit `close-browser=true|false` in the
  VPN profile. Missing, malformed or unreadable values cannot enable closing.
  The prior global `close-windows` preference is deprecated and ignored; users
  should select the new checkbox after upgrading if they want automatic closing.
- GTK forms use a wider scrollable viewport so fields stay reachable on small
  screens. Plasma has larger initial/minimum dimensions. A new README screenshot
  was rendered from the actual GTK4 editor with a fictional profile.
- GNOME 42-44 artifacts are generated from the shared modern entry point/tracker
  when building on Ubuntu 22.04. Modern builds retain 45-51 metadata. GNOME matches
  either the Wayland display or the X11 display to its own session.
- The KDE adapter loads a per-activation KWin 5/6 script under the desktop user's
  identity, waits for the pre-launch window snapshot, preserves the exact window
  reference, validates NM owner/object/UUID/state, and unloads the script on exit.
  It never changes persistent KWin settings or kills a browser process.
- Repeated SAML claims invalidate closing. Review caught a startup race before
  the first helper exported its bus object: a second claim now also writes a
  private persistent cancellation marker, so invalidation survives that race or
  a helper timeout. Claims are pruned after the active connection disappears.
  A subsequent review also bound acknowledgements/polls to the original KWin
  sender; only cancellation may come from another helper.
- Both Ubuntu desktop paths receive the bridge through the core package with
  Python GI/NM introspection dependencies. The Arch recipe includes the adapter
  and GTK editors; native Plasma editor packages remain in the Ubuntu matrix.
  Arch package release 7 contains the refreshed exported source patch.

The implementation was checked against the tagged upstream APIs:
[GNOME Mutter 42 display API](https://github.com/GNOME/mutter/blob/42.0/src/meta/display.h),
[KWin 5.24 scripting](https://github.com/KDE/kwin/blob/v5.24.0/src/scripting/scripting.cpp),
[KWin 5.24 workspace](https://github.com/KDE/kwin/blob/v5.24.0/src/scripting/workspace_wrapper.h),
[KWin 6.0 scripting](https://github.com/KDE/kwin/blob/v6.0.0/src/scripting/scripting.cpp),
[KWin 6.0 workspace](https://github.com/KDE/kwin/blob/v6.0.0/src/scripting/workspace_wrapper.h).

### Verification and limits

- Full non-root suite: **2611 passed, 47 skipped**.
- Full root namespace suite: **2641 passed, 16 skipped, 1 failed**, the same
  previously reproduced desktop runtime-directory assertion described above.
- After the final compositor-sender guard, all **35 changed KWin/legacy/package tests**
  passed again in both root and non-root namespaces. The new negative test
  rejected an acknowledgement from a different compositor before the guard.
- GJS: **54 tracker**, **284 GNOME lifecycle/profile/session**, and **216 KWin
  adapter** assertions passed. Negative tests rejected the old global opt-in's
  ability to override an unchecked profile before the fix. KWin tests caught
  mutable snapshots, non-boolean close flags and the cancellation race before
  their fixes.
- Real GTK3 and GTK4 widgets passed missing/invalid defaults, true/false load/save
  round trips and scroll-layout checks on temporary Broadway displays. Both
  plugins compiled, and Qt's UI compiler accepted the Plasma form. CI now runs
  the GTK preference checks under Xvfb and stages both GNOME variants.
- Arch release 7 rebuilt successfully after the final adapter fix and passed
  package identity/content verification, including the new control in both GTK
  editor binaries. A stale-editor regression failed before the checker was
  strengthened. Generated artifacts are not committed.
- Source whitespace and documentation links are checked separately from generated
  git-patch context.

This machine has no local CMake/KF development environment for compiling Plasma;
the Ubuntu 5/6 package matrix must pass on the new head. New code has not been
installed over the user's working VPN. Live GNOME 42, Plasma 5/6, X11 and new
checkbox tests remain required. Previous successful live tests cover the earlier
GNOME Wayland implementation only. Package builds and fake windows do not prove
live compatibility with each identity provider or browser.

Current-head review passes and CI status are recorded in PR #1. The fork APT
repository remains unpublished; no merge, tag or release is part of this work.
