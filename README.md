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

## Current platform notes

- `kaku init` and managed shell integration remain macOS-only in this first
  Windows port. The terminal starts PowerShell directly, and `kaku.exe` and
  `k.exe` are included beside the GUI.
- Windows toast notifications are currently disabled.
- The Windows Build workflow compiles on a Windows runner. GUI behavior should
  still be checked on a Windows desktop before treating this preview as
  production-ready.

## License and attribution

Kaku for Windows is distributed under the MIT license. See
[`LICENSE.md`](LICENSE.md) and [`NOTICE.md`](NOTICE.md) for upstream credits,
font licenses, and Windows runtime notices.
