#!/usr/bin/env python3
"""Construir un .deb de fuentes Python, sin instalar ni ejecutar scripts root."""
from pathlib import Path
import argparse
from importlib.metadata import distribution, PackageNotFoundError
import platform
import stat
import hashlib
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--qt', choices=('bundled', 'system'), default='bundled',
                    help='bundled incluye Qt para Mint 22/Ubuntu 24.04+; system usa paquetes de Ubuntu 26.04')
args = parser.parse_args()
bundled = args.qt == 'bundled'
architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() if bundled else 'all'
vendor_distributions = []
if bundled:
    try:
        vendor_distributions = [distribution(name) for name in ('PySide6_Essentials', 'shiboken6')]
    except PackageNotFoundError:
        parser.error('Usa .venv/bin/python scripts/build-deb.py con PySide6_Essentials y shiboken6 instalados.')
    if vendor_distributions[0].version != vendor_distributions[1].version:
        parser.error('Las versiones de PySide6_Essentials y shiboken6 deben coincidir.')
    if architecture != 'amd64' or platform.machine() != 'x86_64':
        parser.error('La variante incluida está validada inicialmente sólo para amd64.')
    if any('manylinux' not in dist.read_text('WHEEL') or 'x86_64' not in dist.read_text('WHEEL') for dist in vendor_distributions):
        parser.error('Se requieren wheels Linux x86_64 para incluir el runtime.')
graphical_dependencies = (
    'libc6 (>= 2.39), libstdc++6, libgcc-s1, libegl1, libgl1, libopengl0, '
    'libglib2.0-0t64, libfontconfig1, libfreetype6, libdbus-1-3, zlib1g, '
    'libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, '
    'libxcb-keysyms1, libxcb-render-util0, libxcb-xkb1, libxcb-shape0, '
    'libxcb-randr0, libxcb-sync1, libxcb-xfixes0, libx11-xcb1, '
    'libsm6, libice6, libxrender1, libwayland-client0, libwayland-cursor0, libwayland-egl1'
    if bundled else 'python3-pyside6.qtwidgets (>= 6.8)'
)
OUT = ROOT/'dist'
OUT.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='vpn-manager-deb-') as temporary:
    stage = Path(temporary)/'package'
    def put(relative, text, mode=0o644):
        path = stage/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)
    put('DEBIAN/control', f'''Package: vpn-manager
Version: {VERSION}
Section: net
Priority: optional
Architecture: {architecture}
Maintainer: Luthi
Depends: python3 (>= 3.12), {graphical_dependencies}, python3-dbus, wireguard-tools, iproute2, sudo, pkexec, apparmor
Suggests: openvpn3
Description: Gestor grafico de OpenVPN 3 y WireGuard
 Biblioteca de perfiles, estado de conexiones y habilitacion inicial limitada.
 {'Qt privado incluido para Mint 22 y Ubuntu 24.04 o posterior.' if bundled else 'Qt del sistema para Ubuntu 26.04.'}
''')
    destination = stage/'usr/lib/python3/dist-packages/vpn_manager'
    for source in (ROOT/'src/vpn_manager').rglob('*.py'):
        target = destination/source.relative_to(ROOT/'src/vpn_manager')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)
    if bundled:
        vendor = stage/'usr/lib/vpn-manager/vendor'
        for dist in vendor_distributions:
            for relative in dist.files:
                # RECORD del wheel es la lista permitida, no copiar todo site-packages.
                if relative.is_absolute() or '..' in relative.parts or '__pycache__' in relative.parts or relative.suffix == '.pyc':
                    continue
                source = Path(dist.locate_file(relative))
                if not source.is_file():
                    continue
                target = vendor/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
        put('usr/share/doc/vpn-manager/bundled-runtime.txt',
            '\n'.join(f'{dist.metadata["Name"]}=={dist.version}' for dist in vendor_distributions) +
            '\nQt for Python: https://code.qt.io/pyside/pyside-setup.git/\n'
            'Qt: https://code.qt.io/cgit/qt/\n'
            'Runtime dynamically linked; private libraries may be replaced by the administrator.\n'
            'License notices and component sources: see the upstream repositories above at the bundled release tags.\n')
        put('usr/share/doc/vpn-manager/LGPL-3', Path('/usr/share/common-licenses/LGPL-3').read_text())
        put('usr/share/doc/vpn-manager/GPL-3', Path('/usr/share/common-licenses/GPL-3').read_text())
    # dpkg conoce estos archivos y los retira al desinstalar.
    for source, filename, mode in [('privileged_wireguard.py', 'wireguard-helper', 0o755),
                                  ('wireguard_config.py', 'wireguard_config.py', 0o644)]:
        put('usr/libexec/vpn-manager/'+filename, (ROOT/'src/vpn_manager/system'/source).read_text(), mode)
    vendor_path = "import sys\nsys.path.insert(0, '/usr/lib/vpn-manager/vendor')\n" if bundled else ''
    put('usr/bin/vpn-manager', '#!/usr/bin/python3 -I\n' + vendor_path + 'from vpn_manager.main import main\nraise SystemExit(main())\n', 0o755)
    put('usr/share/applications/vpn-manager.desktop', '''[Desktop Entry]
Type=Application
Name=VPN Manager
Comment=Gestionar OpenVPN 3 y WireGuard
Exec=vpn-manager
Icon=network-vpn
Terminal=false
Categories=Network;
StartupNotify=true
''')
    put('usr/share/doc/vpn-manager/README', (ROOT/'docs/distribution.md').read_text())
    put('DEBIAN/postrm', (ROOT/'packaging/debian/postrm').read_text(), 0o755)
    # El umask del entorno de desarrollo no debe producir directorios escribibles por el grupo.
    for directory in stage.rglob('*'):
        if directory.is_dir(): directory.chmod(0o755)
    stage.chmod(0o755)
    # Installed-Size: KiB por archivo redondeados hacia arriba y 1 KiB por directorio.
    installed_kib = 0
    for path in stage.rglob('*'):
        if path.relative_to(stage).parts[0] == 'DEBIAN':
            continue
        info = path.lstat()
        installed_kib += ((info.st_size + 1023) // 1024
                          if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) else 1)
    control = stage/'DEBIAN/control'
    control.write_text(control.read_text().replace(
        f'Version: {VERSION}\n', f'Version: {VERSION}\nInstalled-Size: {installed_kib}\n', 1))
    archive = OUT/f'vpn-manager_{VERSION}_{architecture}.deb'
    subprocess.run(['dpkg-deb', '--root-owner-group', '-Zzstd', '-z6', '--threads-max=2', '--build', str(stage), str(archive)], check=True)
    archive.with_suffix('.deb.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(archive)
    print(f'Versión: {VERSION}; tamaño instalado estimado: {installed_kib / 1024:.1f} MiB; archivo .deb: {archive.stat().st_size / 1024**2:.1f} MiB')
