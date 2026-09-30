#!/usr/bin/env python3
"""Download and verify Windows assets from the shared PowerShell manifest."""
import hashlib
from pathlib import Path
import re
import urllib.request

root = Path(__file__).resolve().parent.parent
manifest = (root / "scripts/download_windows_assets.ps1").read_text()
commit = re.search(r"\$commit = '([0-9a-f]+)'", manifest).group(1)
for name, expected in re.findall(r"Path = '([^']+)'; Sha256 = '([0-9a-f]+)'", manifest):
    destination = root / "assets/windows" / name
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
        continue
    print("Downloading", name, flush=True)
    data = urllib.request.urlopen(
        f"https://raw.githubusercontent.com/wez/wezterm/{commit}/assets/windows/{name}",
        timeout=120,
    ).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"SHA-256 mismatch for {name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
