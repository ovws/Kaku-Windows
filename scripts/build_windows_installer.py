#!/usr/bin/env python3
"""Build a per-user Inno Setup 7 installer from a verified Windows package."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
parser.add_argument('--version', required=True)
parser.add_argument('--iscc', default=shutil.which('ISCC.exe') or shutil.which('iscc'),
                    help='Path to the Inno Setup 7 x64 command-line compiler')
parser.add_argument('--wine', help='Optional Wine64 executable when building on Linux')
parser.add_argument('--wine-prefix', type=Path, help='Wine prefix, only used with --wine')
args = parser.parse_args()
if not args.iscc:
    parser.error('Install Inno Setup 7 or supply --iscc')
if args.wine_prefix and not args.wine:
    parser.error('--wine-prefix requires --wine')
if os.name != 'nt' and not args.wine:
    parser.error('On Linux, supply --wine and --iscc')
if not args.version or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-' for c in args.version):
    parser.error('Version must contain only letters, digits, dots and hyphens')
stage = args.stage.resolve()
out = args.output_dir.resolve()
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
def path_for_compiler(path):
    path = str(Path(path).resolve())
    return 'Z:' + path.replace('/', '\\') if args.wine else path
def quote(value):
    return str(value).replace('"', '""').replace('{', '{{')
core = [p for p in files if p not in ('kaku-gui.exe', 'kaku.lua') and not p.startswith('mesa/')]
mesa = [p for p in files if p.startswith('mesa/')]
lines = []
for name in core + mesa:
    parent = str(Path(name).parent).replace('/', '\\')
    dest = '{app}' if parent == '.' else '{app}\\' + quote(parent)
    line = f'Source: "{quote(path_for_compiler(stage / name))}"; DestDir: "{dest}"; Flags: ignoreversion'
    if name == 'Kaku.exe':
        line += '; AfterInstall: EnsureGuiAlias'
    if name in mesa:
        line += '; Tasks: mesa'
    lines.append(line)
icon = root / 'assets/windows/kaku.ico'
values = {'VERSION': args.version, 'OUTPUT_DIR': quote(path_for_compiler(out)),
          'FILES': '\n'.join(lines), 'CONFIG': quote(path_for_compiler(stage / 'kaku.lua')),
          'ICON': quote(path_for_compiler(icon)),
          'LOGO': quote(path_for_compiler(root / 'assets/logo.png'))}
template = (root / 'scripts/windows/installer.iss.in').read_text()
for key, value in values.items():
    template = template.replace('@' + key + '@', value)
out.mkdir(parents=True, exist_ok=True)
source = out / 'installer.iss'
source.write_text(template, encoding='utf-8-sig')
env = os.environ.copy()
if args.wine_prefix:
    env['WINEPREFIX'] = str(args.wine_prefix.resolve())
command = [args.iscc, path_for_compiler(source)]
if args.wine:
    command.insert(0, args.wine)
subprocess.run(command, env=env, check=True)
exe = out / f'Kaku-Windows-{args.version}-Setup.exe'
with exe.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
(out / 'SHA256SUMS-installer.txt').write_text(f'{digest}  {exe.name}\n', encoding='ascii')
core_bytes = sum((stage / p).stat().st_size for p in core) + (stage / 'kaku.lua').stat().st_size + icon.stat().st_size
mesa_bytes = sum((stage / p).stat().st_size for p in mesa)
print(f'Default payload: {core_bytes / 1024**2:.1f} MiB; optional Mesa: {mesa_bytes / 1024**2:.1f} MiB')
print(exe)
