<div align="center">
  <img src="assets/logo.png" alt="Kaku" width="112" />
  <h1>Kaku for Windows</h1>
  <p><em>A Windows port of Kaku, the WezTerm-based terminal for AI coding.</em></p>
  <p>
    <a href="https://github.com/tw93/Kaku">Upstream Kaku</a> ·
    <a href="https://github.com/ovws/Kaku-Windows/releases/latest">Windows downloads</a>
  </p>
</div>

This repository adds a Windows desktop build to [Kaku](https://github.com/tw93/Kaku),
which is based on [WezTerm](https://github.com/wez/wezterm). It restores the
Windows windowing backend, uses ConPTY for local shells, and keeps Kaku's tabs,
panes, themes, bundled fonts, and AI features.

This is an independent community port. It is not an official Windows release
from the Kaku maintainer.

## Download and run

Download **Kaku-Windows-x64.zip** from the
[latest Release](https://github.com/ovws/Kaku-Windows/releases/latest), extract
the complete folder, and run `Kaku.exe`. Keep the helper executables and runtime
DLLs beside `Kaku.exe`; the ZIP contains the complete application bundle.

The Windows build targets 64-bit Windows 10 and 11. Windows PowerShell is the
default shell. The bundled Kaku config maps Command-key shortcuts to Windows
Ctrl/Alt shortcuts.

## Build from source

Install Rust 1.95.0 and the Visual Studio C++ Build Tools, then run these
commands in PowerShell from the repository root:

```powershell
./scripts/download_windows_assets.ps1
cargo build --locked --profile release-opt -p kaku -p kaku-gui
```

The build script pins each downloaded Windows runtime file to a WezTerm source
revision and checks its SHA-256 digest. See
[`assets/windows/README.md`](assets/windows/README.md) for third-party notices.

To build a release package, run the **Windows Build** workflow from the Actions
tab. Leave `release_tag` blank for a build artifact; set it to a tag such as
`v0.1.0` to publish the ZIP, the main executable, and SHA-256 checksums in a
GitHub Release.

## Local upstream monitoring and builds

GitHub Actions is optional. `bash scripts/check_upstream_local.sh` fetches
upstream main into a tracking ref and reports pending commits without changing
the working branch. The Memoh local scheduled task can perform this check daily,
prepare an isolated merge, resolve Windows compatibility changes, and run
`bash scripts/build_windows_cross.sh` to generate a local ZIP and SHA-256 file.
Use a dedicated worktree with a fresh `dist` directory for each candidate so
previous packages and user changes remain intact. Failed merges/builds must be
reported rather than published. Local cross-builds still require Windows smoke
testing before release. The scheduled task depends on Memoh and its build
runtime being available; it does not depend on a GitHub paid plan or workflow
write permissions.

## Following upstream updates

The active upstream monitor runs locally through Memoh. An optional GitHub
Actions monitoring workflow has been prepared locally but is not deployed:
the GitHub connection lacks workflow write permission. The local monitor
remains independent of GitHub Actions.

From a clean checkout of the Windows main branch, run:

```bash
bash scripts/sync_upstream.sh           # upstream main
bash scripts/sync_upstream.sh V0.21.0   # example: a specific upstream tag
```

The script creates a `sync/upstream-<commit>` branch and merges upstream while
retaining Windows commits. Resolve conflicts on that branch, preserving the
Windows backend, Cargo patches, runtime assets, bundled config and packaging.
Review upstream workflow changes before pushing. Build the candidate locally
with `bash scripts/build_windows_cross.sh` and review any lockfile changes.
The existing **Windows Build** workflow also runs on main pushes or manual
dispatch; PR builds and stricter lockfile validation are prepared locally
but have not been deployed.

Test the resulting ZIP on Windows: startup, PowerShell, tabs, panes, shortcuts,
fonts and AI chat. Merge after validation, then dispatch **Windows Build** on
main with a unique `release_tag` (for example `v0.21.0-windows.1`) to publish.
For several Windows fixes on the same upstream version, increment the Windows
suffix. Record the upstream commit and Windows smoke result in release notes.
The local scheduled check depends on Memoh and its build runtime being
available. It does not automatically publish releases.

## Windows rendering compatibility

Windows defaults to OpenGL. A user reported glyph bottoms being clipped on
every line with WebGPU; switching to OpenGL restored complete glyphs on that
machine. This is a compatibility workaround; the exact WebGPU/driver cause
has not been established, and additional Windows hardware needs testing.
Font size and line height retain their existing defaults.

To compare WebGPU explicitly, start a fresh instance from PowerShell:

```powershell
.\Kaku.exe --config 'front_end="WebGpu"'
```

Before release, test `gypqj 中文测试`, multiline output, scrolling both ways,
window resize/maximize and monitor DPI changes with both rendering modes.
Existing user configs that explicitly choose WebGPU should be changed to
`config.front_end = 'OpenGL'` if they encounter clipping.

## Current platform notes

- Windows uses the native title bar with minimize, maximize and close buttons.
  Closing a window keeps the existing running-task confirmation behavior.

- Windows exits the GUI after the last shell/window closes, including when
  PowerShell exits via `exit`. Other open panes and windows remain active.

- `kaku init` and managed shell integration remain macOS-only in this first
  Windows port. The terminal starts PowerShell directly. `kaku-cli.exe` is
  the CLI companion, `kaku-gui.exe` is its GUI delegation target, and `k.exe`
  opens AI chat. Keep all three beside `Kaku.exe`.
- Windows toast notifications are currently disabled.
- The Windows Build workflow compiles on a Windows runner. GUI behavior should
  still be checked on a Windows desktop before treating this preview as
  production-ready.

## License and attribution

Kaku for Windows is distributed under the MIT license. See
[`LICENSE.md`](LICENSE.md) and [`NOTICE.md`](NOTICE.md) for upstream credits,
font licenses, and Windows runtime notices.
