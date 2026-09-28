# Windows runtime assets

The Windows build downloads its runtime assets from the pinned WezTerm source
revision `b09b56c29c1e367e598b60ca266e2cc9038751e0` with
[`scripts/download_windows_assets.ps1`](../../scripts/download_windows_assets.ps1).
The script checks a SHA-256 digest for every downloaded file before the build
uses it.

- `conpty.dll` and `OpenConsole.exe` come from Microsoft's Windows Terminal
  project and are distributed under its MIT license. See
  [`conhost-README.md`](conhost-README.md).
- `libEGL.dll` and `libGLESv2.dll` are ANGLE runtime libraries. ANGLE is
  distributed under the BSD 3-Clause license.
- `mesa/opengl32.dll` is a Mesa software OpenGL runtime. Its licensing details
  are linked from [`mesa-README.md`](mesa-README.md).
- `terminal.ico`, `manifest.manifest`, and `console.manifest` are from the
  pinned WezTerm source revision and retain their upstream notices.

These runtime files are included in the Windows Release package, not checked in
as binary source assets.
