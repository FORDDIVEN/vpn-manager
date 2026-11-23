#!/usr/bin/python3 -I
"""Instalación inicial explícita. No inicia VPN ni modifica rutas/DNS."""
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile

DESTINATION = Path('/usr/libexec/vpn-manager')
BROKER = DESTINATION / 'wireguard-helper'
SUDOERS = Path('/etc/sudoers.d')
HEADER = '# Managed by VPN Manager: constrained WireGuard broker v4\n'
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}


def rule(username):
    if username == 'ALL' or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*\$?', username):
        raise ValueError('Nombre de cuenta no compatible con la configuración automática.')
    return HEADER + f'{username} ALL=(root) NOPASSWD: {BROKER} ""\n'


def directory(path, mode=0o755):
    path.mkdir(mode=mode, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Una carpeta de instalación no tiene permisos seguros.')


def atomic_write(path, data, mode):
    descriptor, name = tempfile.mkstemp(prefix='.vpn-manager-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def check(arguments, *, input=None):
    result = subprocess.run(arguments, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=ENV, timeout=30, check=False)
    if result.returncode:
        raise ValueError('No se pudo validar la configuración de permisos; se restaurará el estado anterior.')
    return result


APPARMOR_PROFILE = Path('/etc/apparmor.d/wg-quick')
APPARMOR_LOCAL = Path('/etc/apparmor.d/local/wg-quick')
APPARMOR_PARSER = '/usr/sbin/apparmor_parser'
APPARMOR_BEGIN = '# BEGIN VPN Manager: WireGuard access'
APPARMOR_END = '# END VPN Manager: WireGuard access'
APPARMOR_RULES = (
    '/var/lib/vpn-manager/wireguard/[0-9]*/[0-9a-f]*-*/vm*.conf r,\n'
    '/etc/nsswitch.conf r,\n'
    '/etc/passwd r,\n'
)


def apparmor_files():
    if not APPARMOR_PROFILE.exists():
        return {}
    for path in (APPARMOR_PROFILE.parent, APPARMOR_PROFILE):
        info = path.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or path.is_symlink():
            raise ValueError('El perfil AppArmor no tiene permisos seguros.')
    if not APPARMOR_PROFILE.is_file():
        raise ValueError('Perfil AppArmor inválido.')
    profile = APPARMOR_PROFILE.read_text()
    if not re.search(r'^\s*(?:#)?include\s+(?:if\s+exists\s+)?<local/wg-quick>\s*$', profile, re.M):
        raise ValueError('El perfil AppArmor no admite el ajuste local esperado; se conserva sin modificar.')
    if not Path(APPARMOR_PARSER).is_file():
        raise ValueError('Falta apparmor_parser para validar el ajuste de WireGuard.')
    directory(APPARMOR_LOCAL.parent)
    current = ''
    if APPARMOR_LOCAL.exists() or APPARMOR_LOCAL.is_symlink():
        info = APPARMOR_LOCAL.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Los ajustes locales AppArmor tienen permisos inseguros.')
        current = APPARMOR_LOCAL.read_text()
    if current.count(APPARMOR_BEGIN) != current.count(APPARMOR_END) or current.count(APPARMOR_BEGIN) > 1:
        raise ValueError('El bloque administrado AppArmor está incompleto; se conserva sin modificar.')
    block = APPARMOR_BEGIN + '\n' + APPARMOR_RULES + APPARMOR_END
    if APPARMOR_BEGIN in current:
        start, end = current.index(APPARMOR_BEGIN), current.index(APPARMOR_END) + len(APPARMOR_END)
        if end < start:
            raise ValueError('Bloque AppArmor inválido.')
        result = current[:start] + block + current[end:]
    else:
        result = current + ('\n' if current and not current.endswith('\n') else '') + block + '\n'
    return {APPARMOR_LOCAL: (result.encode(), 0o644)}


def install(uid, username):
    policy = rule(username).encode()
    # No editar /etc/sudoers ni conceder acceso directo a wg-quick, shells o Python.
    for path in (Path('/usr'), Path('/usr/libexec'), DESTINATION, SUDOERS):
        directory(path)
    lock_path = DESTINATION / '.installation.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = Path(__file__).parent
        files = {
            DESTINATION / 'wireguard_config.py': ((source / 'wireguard_config.py').read_bytes(), 0o644),
            BROKER: ((source / 'privileged_wireguard.py').read_bytes(), 0o755),
            SUDOERS / f'vpn-manager-{uid}': (policy, 0o440),
        }
        armor = apparmor_files()
        files.update(armor)
        backups = {}
        for path in files:
            if path.is_symlink():
                raise ValueError('No se reemplazará un enlace simbólico en el destino.')
            if path.exists():
                info = path.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                    raise ValueError('Un archivo de destino tiene permisos inseguros.')
                backups[path] = (path.read_bytes(), stat.S_IMODE(info.st_mode))
            else:
                backups[path] = None
        policy_path = SUDOERS / f'vpn-manager-{uid}'
        if backups[policy_path] and not backups[policy_path][0].startswith(b'# Managed by VPN Manager:'):
            raise ValueError('Ya existe una política no administrada por esta aplicación; no se sobrescribirá.')
        candidate = SUDOERS / f'.vpn-manager-{uid}-candidate'
        try:
            atomic_write(candidate, policy, 0o440)
            check(['/usr/sbin/visudo', '-c', '-f', str(candidate)])
        finally:
            candidate.unlink(missing_ok=True)
        changed = []
        armor_reload_attempted = False
        try:
            for path, (data, mode) in files.items():
                atomic_write(path, data, mode)
                changed.append(path)
            check(['/usr/sbin/visudo', '-c'])
            if armor:
                # Compilar sin cargar ni usar caché; sólo entonces sustituir el perfil activo.
                check([APPARMOR_PARSER, '-Q', '-K', str(APPARMOR_PROFILE)])
                armor_reload_attempted = True
                check([APPARMOR_PARSER, '-r', '-K', str(APPARMOR_PROFILE)])
            # Verificar la autorización como la cuenta destino, no como root.
            result = check(['/usr/bin/sudo', '-u', username, '--', '/usr/bin/sudo', '-n', '--', str(BROKER)],
                           input=b'{"operation":"probe"}\n')
            response = json.loads(result.stdout)
            if not response.get('ready') or response.get('uid') != uid:
                raise ValueError('La comprobación del permiso instalado no fue satisfactoria.')
        except Exception:
            for path in reversed(changed):
                previous = backups[path]
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, *previous)
            if armor_reload_attempted:
                try:
                    check([APPARMOR_PARSER, '-r', '-K', str(APPARMOR_PROFILE)])
                except Exception:
                    raise ValueError('Archivos restaurados, pero no se pudo recargar el perfil AppArmor anterior. Revisa AppArmor antes de reintentar.') from None
            raise
    return {'ready': True, 'uid': uid, 'version': 4}


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1 or not os.environ.get('PKEXEC_UID', '').isdecimal():
        raise ValueError('La habilitación requiere autorización administrativa desde la aplicación.')
    uid = int(os.environ['PKEXEC_UID'])
    if uid == 0:
        raise ValueError('Inicia la GUI con una cuenta de usuario normal.')
    return install(uid, pwd.getpwuid(uid).pw_name)


if __name__ == '__main__':
    try:
        print(json.dumps({'ok': True, **main()}), flush=True)
    except ValueError as error:
        print(json.dumps({'error': str(error)}), flush=True)
        sys.exit(1)
    except Exception:
        print(json.dumps({'error': 'No se pudo completar la habilitación administrativa.'}), flush=True)
        sys.exit(1)
