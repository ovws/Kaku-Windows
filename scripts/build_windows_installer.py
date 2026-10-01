#!/usr/bin/env python3
"""Build a per-user NSIS installer from a verified Windows portable package."""
import argparse
import hashlib
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
parser.add_argument('--version', required=True)
args = parser.parse_args()
stage = args.stage.resolve()
out = args.output_dir.resolve()
# Version is displayed in NSIS source and used in a filename.
if not args.version or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-' for c in args.version):
    parser.error('Version must contain only letters, digits, dots and hyphens')
required = ['Kaku.exe', 'kaku-gui.exe', 'kaku-cli.exe', 'k.exe', 'kaku.lua',
            'conpty.dll', 'OpenConsole.exe', 'libEGL.dll', 'libGLESv2.dll',
            'fonts/JetBrainsMono-Regular.ttf', 'fonts/SymbolsNerdFontMono-Regular.ttf',
            'LICENSE.md', 'NOTICE.md', 'mesa/opengl32.dll']
for name in required:
    if not (stage / name).is_file():
        raise SystemExit(f'Missing package file: {name}')
if (stage / 'Kaku.exe').read_bytes() != (stage / 'kaku-gui.exe').read_bytes():
    raise SystemExit('GUI binaries differ; cannot deduplicate them')
files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file())
if len(files) != len({p.casefold() for p in files}):
    raise SystemExit('Windows filename collision')
# Escape NSIS literal strings, including paths supplied by the caller.
def quote(value):
    return str(value).replace('$', '$$').replace('"', '$\\"')
def win(value):
    return value.replace('/', '\\')
core = [p for p in files if p not in ('kaku-gui.exe', 'kaku.lua') and not p.startswith('mesa/')]
mesa = [p for p in files if p.startswith('mesa/')]
def install_lines(names):
    result = []
    for name in names:
        parent = win(str(Path(name).parent))
        suffix = '' if parent == '.' else '\\' + quote(parent)
        result += [f'SetOutPath "$INSTDIR{suffix}"', f'File "{quote(stage / name)}"']
    return '\n'.join(result)
# Delete only known payload files; preserve config and user-created files.
remove = [p for p in files if p != 'kaku.lua']
uninstall = '\n'.join(f'Delete "$INSTDIR\\{quote(win(p))}"' for p in remove)
dirs = sorted({str(Path(p).parent) for p in remove if str(Path(p).parent) != '.'}, key=lambda p: (p.count('/'), p), reverse=True)
uninstall += '\n' + '\n'.join(f'RMDir "$INSTDIR\\{quote(win(p))}"' for p in dirs)
out.mkdir(parents=True, exist_ok=True)
exe = out / f'Kaku-Windows-{args.version}-Setup.exe'
template = (root / 'scripts/windows/installer.nsi.in').read_text()
values = {'VERSION': args.version, 'OUTPUT': quote(exe), 'LICENSE': quote(stage / 'LICENSE.md'),
          'CORE_FILES': install_lines(core), 'MESA_FILES': install_lines(mesa),
          'CONFIG': quote(stage / 'kaku.lua'), 'UNINSTALL_FILES': uninstall}
for key, value in values.items():
    template = template.replace('@' + key + '@', value)
source = out / 'installer.nsi'
source.write_text(template, encoding='utf-8')
subprocess.run(['makensis', '-V3', str(source)], check=True)
with exe.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
(out / 'SHA256SUMS-installer.txt').write_text(f'{digest}  {exe.name}\n', encoding='ascii')
core_bytes = sum((stage / p).stat().st_size for p in core) + (stage / 'kaku.lua').stat().st_size
mesa_bytes = sum((stage / p).stat().st_size for p in mesa)
print(f'Default payload: {core_bytes / 1024**2:.1f} MiB; optional Mesa: {mesa_bytes / 1024**2:.1f} MiB')
print(exe)
