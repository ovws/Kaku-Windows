#!/usr/bin/env python3
"""Exercise install/upgrade/uninstall in a temporary native Windows directory."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('installer', type=Path)
args = parser.parse_args()
if sys.platform != 'win32':
    raise SystemExit('Run this smoke test on native Windows')
installer = args.installer.resolve()
def install(directory, mesa=False):
    subprocess.run([str(installer), '/S'] + (['/MESA'] if mesa else []) + [f'/D={directory}'], check=True, timeout=180)
def uninstall(directory):
    subprocess.run([str(directory / 'Uninstall.exe'), '/S', f'_?={directory}'], check=True, timeout=120)
with tempfile.TemporaryDirectory(prefix='kaku-installer-') as scratch:
    target = Path(scratch) / 'Kaku'
    install(target)
    for name in ['Kaku.exe', 'kaku-gui.exe', 'kaku-cli.exe', 'k.exe', 'kaku.lua', 'conpty.dll', 'libEGL.dll', 'libGLESv2.dll', 'kaku.ico']:
        assert (target / name).is_file(), name
    assert os.path.samefile(target / 'Kaku.exe', target / 'kaku-gui.exe'), 'GUI hard link missing on NTFS'
    assert not (target / 'mesa/opengl32.dll').exists(), 'Mesa must be optional'
    subprocess.run([str(target / 'kaku-cli.exe'), '--version'], check=True, timeout=30)
    print('Default installation, NTFS hard link and CLI startup: PASS', flush=True)
    config = target / 'kaku.lua'
    content = config.read_bytes() + b'\n-- preserve-config smoke\n'
    config.write_bytes(content)
    note = target / 'user-note.txt'
    note.write_text('keep me')
    install(target)
    assert config.read_bytes() == content
    assert os.path.samefile(target / 'Kaku.exe', target / 'kaku-gui.exe')
    print('Upgrade preserves config and GUI hard link: PASS', flush=True)
    uninstall(target)
    assert not (target / 'Kaku.exe').exists()
    assert not (target / 'kaku-cli.exe').exists()
    assert config.read_bytes() == content and note.read_text() == 'keep me'
    print('Uninstall preserves config and user files: PASS', flush=True)
    install(target, mesa=True)
    assert (target / 'mesa/opengl32.dll').is_file()
    print('Optional Mesa installation: PASS', flush=True)
    uninstall(target)
    assert not (target / 'mesa/opengl32.dll').exists()
    print('Optional Mesa uninstall: PASS', flush=True)
