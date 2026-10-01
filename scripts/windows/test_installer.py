#!/usr/bin/env python3
"""Exercise an Inno installer on native Windows or an isolated Wine64 prefix."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('installer', type=Path)
parser.add_argument('--wine')
parser.add_argument('--wine-prefix', type=Path)
parser.add_argument('--scratch-dir', type=Path)
args = parser.parse_args()
if sys.platform != 'win32' and not args.wine:
    parser.error('Run on native Windows, or supply --wine and --wine-prefix')
if args.wine and not args.wine_prefix:
    parser.error('--wine requires an isolated --wine-prefix')
installer = args.installer.resolve()
env = os.environ.copy()
if args.wine:
    env['WINEPREFIX'] = str(args.wine_prefix.resolve())
    env['WINEDEBUG'] = '-all'
    env['WINESERVER'] = '/usr/lib/wine/wineserver64'
def winpath(path):
    path = str(Path(path).resolve())
    return 'Z:' + path.replace('/', '\\') if args.wine else path
def run(exe, params, check=True):
    command = ([args.wine] if args.wine else []) + [str(exe)] + params
    return subprocess.run(command, env=env, check=check, timeout=180)
def install(directory=None, tasks=None):
    options = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-']
    if directory is not None:
        options += ['/DIR=' + winpath(directory)]
    if tasks is not None:
        options += ['/TASKS=' + tasks]
    return run(installer, options)
def uninstall(directory):
    run(directory / 'unins000.exe', ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'])
def reg(*options, check=True):
    exe = 'reg' if args.wine else 'reg.exe'
    return run(exe, list(options), check=check)
legacy_key = r'HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\KakuWindows'
legacy_path_key = r'HKCU\Software\KakuWindows'
if args.scratch_dir:
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='kaku-installer-', dir=args.scratch_dir) as scratch:
    target = Path(scratch) / 'Kaku'
    install(target, tasks='')
    for name in ['Kaku.exe', 'kaku-gui.exe', 'kaku-cli.exe', 'k.exe', 'kaku.lua', 'conpty.dll', 'libEGL.dll', 'libGLESv2.dll', 'kaku.ico']:
        assert (target / name).is_file(), name
    assert os.path.samefile(target / 'Kaku.exe', target / 'kaku-gui.exe'), 'GUI hard link missing'
    assert not (target / 'mesa/opengl32.dll').exists(), 'Mesa must be optional'
    run(target / 'kaku-cli.exe', ['--version'])
    print('Default installation, GUI hard link and CLI startup: PASS', flush=True)
    config = target / 'kaku.lua'
    content = config.read_bytes() + b'\n-- preserve-config smoke\n'
    config.write_bytes(content)
    note = target / 'user-note.txt'
    note.write_text('keep me')
    install(target)
    assert config.read_bytes() == content
    assert os.path.samefile(target / 'Kaku.exe', target / 'kaku-gui.exe')
    print('Upgrade preserves config and GUI hard link: PASS', flush=True)
    if not args.wine:
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(target / 'Kaku.exe'), 0x80000000, 0, None, 3, 0, None)
        assert handle != ctypes.c_void_p(-1).value
        try:
            command = [str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/DIR=' + str(target)]
            assert subprocess.run(command, timeout=60).returncode != 0, 'Upgrade must reject a locked GUI'
        finally:
            kernel.CloseHandle(handle)
        print('Running/locked GUI upgrade protection: PASS', flush=True)
    uninstall(target)
    assert not (target / 'Kaku.exe').exists() and not (target / 'kaku-cli.exe').exists()
    assert config.read_bytes() == content and note.read_text() == 'keep me'
    print('Uninstall preserves config and user files: PASS', flush=True)
    install(target, tasks='mesa')
    assert (target / 'mesa/opengl32.dll').is_file()
    install(target)
    assert (target / 'mesa/opengl32.dll').is_file()
    print('Optional Mesa install and upgrade retention: PASS', flush=True)
    # Build a fixture matching the published NSIS installer's files and registry.
    legacy = Path(scratch) / 'LegacyKaku'
    legacy.mkdir()
    shutil.copy2(target / 'Kaku.exe', legacy / 'Kaku.exe')
    (legacy / 'Uninstall.exe').write_bytes(b'MZ NSIS uninstall metadata fixture')
    (legacy / 'kaku.lua').write_bytes(content)
    (legacy / 'user-note.txt').write_text('legacy user file')
    for key, name, value in [(legacy_path_key, 'InstallDir', winpath(legacy)),
                             (legacy_key, 'InstallLocation', winpath(legacy)),
                             (legacy_key, 'UninstallString', '"' + winpath(legacy / 'Uninstall.exe') + '"')]:
        reg('add', key, '/v', name, '/t', 'REG_SZ', '/d', value, '/f', '/reg:32')
    # Installing elsewhere must not retire the separate legacy installation.
    install(target)
    assert (legacy / 'Uninstall.exe').exists()
    assert reg('query', legacy_key, '/reg:32', check=False).returncode == 0
    print('Separate legacy installation is retained: PASS', flush=True)
    uninstall(target)
    assert not (target / 'mesa/opengl32.dll').exists()
    install(legacy)
    assert (legacy / 'unins000.exe').exists()
    assert not (legacy / 'Uninstall.exe').exists()
    assert (legacy / 'kaku.lua').read_bytes() == content
    assert reg('query', legacy_key, '/reg:32', check=False).returncode != 0
    assert os.path.samefile(legacy / 'Kaku.exe', legacy / 'kaku-gui.exe')
    print('NSIS metadata fixture migrates in place without deleting config: PASS', flush=True)
    uninstall(legacy)
    assert not (legacy / 'Kaku.exe').exists()
    assert (legacy / 'user-note.txt').read_text() == 'legacy user file'
    print('Migrated installation uninstalls safely: PASS', flush=True)
