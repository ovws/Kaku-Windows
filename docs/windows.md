# Kaku for Windows

Kaku for Windows uses the restored Windows backend from WezTerm and the
ConPTY-based local terminal support already present in the source tree.

## Release package

Download `Kaku-Windows-x64.zip`, extract the folder, and start `Kaku.exe`.
Keep `kaku-cli.exe`, `kaku-gui.exe`, `k.exe`, ConPTY, ANGLE, and Mesa files in the extracted folder.
`Kaku.exe` is also listed as a separate Release asset, but it needs the helper
executables and runtime DLLs from the ZIP. The ZIP is the complete runnable
package.

The bundled `kaku.lua` uses `powershell.exe -NoLogo` as its default shell and
maps Kaku's Command-key shortcuts to Ctrl/Alt combinations. Users can edit the
copy beside `Kaku.exe` or place a personal `kaku.lua` in their Kaku config
directory.

## Build

Run from PowerShell with Rust 1.95.0 and Visual Studio C++ Build Tools:

```powershell
./scripts/download_windows_assets.ps1
cargo build --locked --profile release-opt -p kaku -p kaku-gui
```

To build and publish through GitHub Actions, select **Actions → Windows Build →
Run workflow**. Leave `release_tag` empty to create a build artifact. Supplying
a new tag publishes the executable, full ZIP, and checksums as a GitHub
Release.

The downloader pins the upstream WezTerm revision and validates the SHA-256
digest for every Windows runtime asset before compilation. The runtime notices
are in [`../assets/windows/README.md`](../assets/windows/README.md).

## Current limits

The existing `kaku init` command only configures macOS shells. This build starts
PowerShell directly, but does not yet install a PowerShell profile integration.
Windows toast notifications are also disabled.

## Installer

`Kaku-Windows-<version>-Setup.exe` installs for the current user in
`%LOCALAPPDATA%\Programs\Kaku` without administrator privileges. It adds a
Start menu entry and an uninstall entry in Windows Settings. A desktop shortcut
is optional. Inno Setup provides directory and optional-task pages followed by
installation and completion; extra welcome, group and confirmation pages are omitted. The installer, uninstaller and shortcuts use the
Kaku brand icon; the finish page offers to start Kaku. Close Kaku before installing an update.

The default install keeps the CLI, AI helper, fonts, ConPTY and ANGLE. On NTFS,
`Kaku.exe` and `kaku-gui.exe` share the same file data through a hard link, saving
about 36 MiB. Filesystems without hard-link support use a separate copy. Mesa's
software OpenGL fallback is an optional component (about 36 MiB); enable it if
older GPU drivers or remote desktop sessions have OpenGL rendering problems.
The portable ZIP continues to include all runtime libraries.

Upgrades preserve an existing `kaku.lua`; uninstall removes known application
files and leaves configuration and user-created files in place. The installer
is unsigned, so Windows may show an unknown-publisher prompt. Native Windows
installation and rendering checks are still required; Wine checks alone do not
establish Windows compatibility.

To build from a verified portable staging directory, install the x64 edition of
Inno Setup 7.1.0, put `ISCC.exe` on PATH (or pass `--iscc`), and run:

```sh
python3 scripts/build_windows_installer.py \
  --stage dist/Kaku-Windows-x64 \
  --output-dir dist/installer \
  --version 0.21.0-8
```

For unattended installation use `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`.
Add `/TASKS=mesa` for software OpenGL or `/TASKS=desktopicon,mesa` for both
options. Set a custom directory with `/DIR=C:\Apps\Kaku`.

The Inno application ID is fixed across releases. An in-place upgrade detects
the legacy NSIS install directory, preserves its config and retires the old
uninstall entry only after installation succeeds. Installing to a different
directory retains the separate NSIS installation. Do not manually run the old
NSIS uninstaller after an in-place migration.

On Linux, use Wine64 with `--iscc /path/to/ISCC.exe --wine /path/to/wine64
--wine-prefix /path/to/isolated-prefix`. For installer lifecycle validation run
`scripts/windows/test_installer.py <installer>` on native Windows, or add
`--wine`, `--wine-prefix` and a repository-local `--scratch-dir` under Wine.
The legacy migration test uses matching NSIS metadata; it does not execute the
old NSIS installer. The workflow template in
`scripts/windows/windows-installer-workflow.yml` pins and checks the compiler;
it must be enabled with GitHub workflow permissions before native CI can run.
