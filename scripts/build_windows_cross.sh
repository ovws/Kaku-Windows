#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v x86_64-w64-mingw32-gcc >/dev/null
command -v x86_64-w64-mingw32-g++ >/dev/null
python3 scripts/download_windows_assets.py
rustup target add x86_64-pc-windows-gnu --toolchain 1.95.0
cargo +1.95.0 build --locked --target x86_64-pc-windows-gnu --profile release-opt -p kaku -p kaku-gui
python3 scripts/package_windows.py
