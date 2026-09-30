#!/usr/bin/env python3
"""Assemble a Windows x64 package after a successful Cargo build."""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import zipfile

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--build-dir", type=Path,
                    default=root / "target/x86_64-pc-windows-gnu/release-opt")
args = parser.parse_args()
build = args.build_dir.resolve()
dist = root / "dist"
stage = dist / "Kaku-Windows-x64"
# Refuse stale staging files rather than mix two builds.
if stage.exists():
    raise SystemExit(f"Staging directory already exists: {stage}; use a fresh directory")
for name in ("kaku-gui.exe", "kaku.exe", "k.exe", "OpenConsole.exe"):
    if not (build / name).is_file():
        raise SystemExit(f"Missing build output: {name}")
stage.mkdir(parents=True)
for source, name in (("kaku-gui.exe", "Kaku.exe"), ("kaku.exe", "kaku-cli.exe"),
                     ("kaku-gui.exe", "kaku-gui.exe"), ("k.exe", "k.exe"),
                     ("OpenConsole.exe", "OpenConsole.exe")):
    shutil.copy2(build / source, stage / name)
for file in build.glob("*.dll"):
    shutil.copy2(file, stage / file.name)
shutil.copytree(build / "mesa", stage / "mesa")
shutil.copytree(root / "assets/fonts", stage / "fonts")
shutil.copy2(root / "assets/macos/Kaku.app/Contents/Resources/kaku.lua", stage / "kaku.lua")
(stage / "notices").mkdir()
for source, name in (("README.md", "Windows-runtime-assets.txt"),
                     ("conhost-README.md", "Microsoft-ConPTY.txt"), ("mesa-README.md", "Mesa.txt")):
    shutil.copy2(root / "assets/windows" / source, stage / "notices" / name)
shutil.copy2(root / "deps/libssh-rs-sys/vendored/COPYING", stage / "notices/libssh.txt")
shutil.copy2(root / "deps/libssh-rs-sys/README.md", stage / "notices/libssh-rs-sys.txt")
for source, name in (("README.md", "README.txt"), ("LICENSE.md", "LICENSE.md"),
                     ("NOTICE.md", "NOTICE.md")):
    shutil.copy2(root / source, stage / name)
required = ("Kaku.exe", "kaku-cli.exe", "kaku-gui.exe", "k.exe", "kaku.lua",
            "fonts/JetBrainsMono-Regular.ttf", "fonts/SymbolsNerdFontMono-Regular.ttf",
            "conpty.dll", "OpenConsole.exe", "libEGL.dll", "libGLESv2.dll",
            "mesa/opengl32.dll", "notices/Microsoft-ConPTY.txt", "notices/Mesa.txt")
for name in required:
    if not (stage / name).is_file():
        raise SystemExit(f"Missing required file: {name}")
files = sorted(file for file in stage.rglob("*") if file.is_file())
names = [str(file.relative_to(stage)).casefold() for file in files]
if len(names) != len(set(names)):
    raise SystemExit("Package contains names that collide on Windows")
for file in files:
    if file.suffix.lower() in (".exe", ".dll"):
        data = file.read_bytes()
        offset = struct.unpack_from("<I", data, 0x3c)[0]
        if data[:2] != b"MZ" or data[offset:offset+4] != b"PE\0\0" or struct.unpack_from("<H", data, offset+4)[0] != 0x8664:
            raise SystemExit(f"Not a Windows x64 binary: {file}")
zip_path = dist / "Kaku-Windows-x64.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for file in files:
        archive.write(file, file.relative_to(dist))
with zipfile.ZipFile(zip_path) as archive:
    if archive.testzip() is not None:
        raise SystemExit("ZIP integrity check failed")
    for file in files:
        if archive.read(str(file.relative_to(dist))) != file.read_bytes():
            raise SystemExit(f"ZIP contents differ: {file}")
def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
sums = {zip_path: "Kaku-Windows-x64.zip", stage / "Kaku.exe": "Kaku.exe"}
(dist / "SHA256SUMS.txt").write_text(
    "".join(f"{digest(path)}  {name}\n" for path, name in sums.items()), encoding="ascii")
(dist / "release-notes.md").write_text(
    "Kaku for Windows x64\n\nExtract the complete ZIP, then run Kaku.exe.\n"
    "Keep all helper programs, fonts and DLLs in the extracted folder.\n"
    "kaku-cli.exe is the command-line companion; k.exe opens AI chat.\n\n"
    "Built on Linux with Rust 1.95.0 and MinGW. Windows native startup "
    "validation is still required before publishing this build.\n",
    encoding="utf-8")
print(f"Verified {len(files)} files, Windows x64 binaries, ZIP contents and SHA-256.")
print(zip_path)
