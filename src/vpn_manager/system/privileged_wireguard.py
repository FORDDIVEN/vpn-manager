#!/usr/bin/python3 -I
"""Broker instalado por root. Protocolo cerrado por stdin; sin argumentos libres."""
import fcntl
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
from uuid import UUID

VERSION = 4
ROOT = Path('/var/lib/vpn-manager/wireguard')
SYSTEM = Path('/etc/wireguard')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
LIMIT = 2 * 1024 * 1024


def validator():
    path = Path(__file__).with_name('wireguard_config.py')
    if os.geteuid() == 0:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('El validador instalado no tiene permisos seguros.')
    spec = importlib.util.spec_from_file_location('wireguard_config', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize


def private_directory(path):
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Directorio operativo inseguro.')


def identifier(value):
    parsed = str(UUID(value))
    if value != parsed:
        raise ValueError('Identificador inválido.')
    return parsed


def interface(uid, profile_id):
    return 'vm' + hashlib.sha256(f'{uid}:{profile_id}'.encode()).hexdigest()[:12]


def managed_path(uid, profile_id):
    return ROOT / str(uid) / profile_id / (interface(uid, profile_id) + '.conf')


def read_regular(path, owners=(0,), private=True):
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in owners or (private and info.st_mode & 0o077):
            raise ValueError('Archivo de configuración inseguro.')
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('Configuración demasiado grande.')
    return data


def system_profile(uid, filename):
    import re
    if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_=+.-]{1,15}\.conf', filename):
        raise ValueError('Selecciona un .conf directamente en /etc/wireguard.')
    info = SYSTEM.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('La carpeta del sistema no es segura.')
    data = read_regular(SYSTEM / filename, owners=(0, uid), private=bool(info.st_mode & 0o077))
    validator()(data.decode('utf-8-sig'))  # No ejecutar nunca hooks de un perfil importado.
    return data


def publish_system(uid, request):
    """Publicar una copia validada, sin sustituir archivos existentes."""
    import re
    filename = request.get('filename', '')
    if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_=+.-]{1,15}\.conf', filename):
        raise ValueError('Nombre de archivo WireGuard inválido (máximo 15 caracteres antes de .conf).')
    data = validator()(request['config']).encode()
    SYSTEM.mkdir(mode=0o700, exist_ok=True)
    info = SYSTEM.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('La carpeta del sistema no es segura.')
    path = SYSTEM / filename
    existing = list(SYSTEM.glob('*.conf'))
    if not path.exists() and (len(existing) >= 1024 or sum(p.lstat().st_size for p in existing) + len(data) > 64 * 1024 * 1024):
        raise ValueError('Se alcanzó el límite de almacenamiento de perfiles en /etc/wireguard.')
    # Publicar el archivo completo mediante enlace atómico: nunca truncar un perfil ajeno.
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix='.vpn-manager-', dir=SYSTEM)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if system_profile(uid, filename) != data:
                raise ValueError('Ya existe otro perfil con ese nombre en /etc/wireguard. Renombra el archivo que quieres importar.') from None
    finally:
        os.unlink(temporary)
    return metadata(path, data)


def metadata(path, data):
    return {'path': str(path), 'filename': path.name, 'fingerprint': hashlib.sha256(data).hexdigest()}


def command(arguments):
    result = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=ENV, timeout=90, check=False)
    if result.returncode:
        # Clasificar sólo indicadores conocidos; nunca devolver líneas del comando.
        error = result.stderr.decode('utf-8', errors='replace').lower()
        if 'resolvconf: command not found' in error:
            detail = 'Falta resolvconf, necesario para aplicar el DNS del perfil WireGuard.'
        elif 'resolvconf' in error and any(marker in error for marker in ('failed', 'error', 'not found', 'not running', 'refused')):
            detail = 'Falló el soporte DNS (resolvconf). Comprueba su instalación y el servicio de resolución de la VM.'
        elif any(marker in error for marker in ('name or service not known', 'temporary failure in name resolution', 'no address associated with hostname')):
            detail = 'No se pudo resolver el nombre del servidor VPN. Comprueba el DNS y la red de la VM.'
        elif 'operation not permitted' in error or 'permission denied' in error:
            detail = 'El sistema rechazó una operación de red por permisos. Comprueba las restricciones del invitado o contenedor.'
        elif 'operation not supported' in error or 'unknown device type' in error or 'protocol not supported' in error:
            detail = 'El sistema no ofrece el soporte WireGuard necesario. Comprueba el kernel del invitado.'
        elif 'file exists' in error:
            detail = 'Ya existe una interfaz, dirección o ruta requerida. Comprueba conflictos con otras conexiones.'
        elif 'iptables-restore: command not found' in error or 'ip6tables-restore: command not found' in error:
            detail = 'Falta soporte de firewall para las rutas del perfil: instala nftables o iptables en el invitado.'
        else:
            detail = 'Comprueba configuración, rutas, firewall y soporte DNS; la salida sensible permanece oculta.'
        raise ValueError(f'Falló la operación de red (código {result.returncode}). {detail}')
    return result.stdout


def observation(uid, profile_id):
    name = interface(uid, profile_id)
    result = subprocess.run(['/usr/sbin/ip', '-details', '-json', 'address', 'show', 'dev', name],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=ENV, timeout=10, check=False)
    if result.returncode:
        if not Path('/sys/class/net', name).exists():
            return {'state': 'Desconectado', 'ip_addresses': []}
        raise ValueError('No se pudo observar una interfaz existente.')
    devices = json.loads(result.stdout)
    if not devices:
        return {'state': 'Desconectado', 'ip_addresses': []}
    device = devices[0]
    if device.get('linkinfo', {}).get('info_kind') != 'wireguard' or device.get('ifalias') != f'vpn-manager:{uid}:{profile_id}':
        raise ValueError('Interfaz ocupada: no se confirmó su propiedad.')
    return {'state': 'Conectado' if 'UP' in device.get('flags', []) else 'Desconectado', 'interface': name,
            'ip_addresses': [str(ipaddress.ip_address(a['local'])) for a in device.get('addr_info', []) if a.get('local')]}


def cancellation():
    stream = sys.stdin.buffer.raw
    if select.select([stream], [], [], 0)[0]:
        line = stream.readline(1024)
        return bool(line and json.loads(line).get('cancel'))
    return False


def dispatch(uid, request):
    operation = request.get('operation')
    if operation == 'probe':
        policy = Path('/etc/sudoers.d') / f'vpn-manager-{uid}'
        try:
            configured = read_regular(policy, private=False).startswith(
                f'# Managed by VPN Manager: constrained WireGuard broker v{VERSION}\n'.encode())
        except (OSError, ValueError):
            configured = False
        return {'ready': True, 'version': VERSION, 'setup_version': VERSION if configured else 0, 'uid': uid}
    if operation == 'publish-system':
        return publish_system(uid, request)
    if operation == 'list':
        profiles, rejected = [], 0
        for path in sorted(SYSTEM.glob('*.conf')):
            try:
                profiles.append(metadata(path, system_profile(uid, path.name)))
            except (OSError, ValueError, UnicodeError):
                rejected += 1
        return {'profiles': profiles, 'rejected': rejected}
    if operation not in ('register', 'register-system', 'inspect', 'connect', 'disconnect', 'cancel', 'status'):
        raise ValueError('Operación no permitida.')
    profile_id = identifier(request['id'])
    path = managed_path(uid, profile_id)
    if operation == 'status':
        return observation(uid, profile_id)
    private_directory(ROOT.parent)
    private_directory(ROOT)
    private_directory(ROOT / str(uid))
    lock_path = ROOT / str(uid) / 'operations.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if operation in ('register', 'register-system'):
            # No reemplazar la configuración mientras exista su interfaz.
            if Path('/sys/class/net', interface(uid, profile_id)).exists():
                raise ValueError('Desconecta el perfil antes de registrar una nueva revisión.')
            if operation == 'register-system':
                raw = system_profile(uid, request['filename'])
                if hashlib.sha256(raw).hexdigest() != request['fingerprint']:
                    raise ValueError('El perfil del sistema cambió; vuelve a seleccionarlo.')
                text = raw.decode('utf-8-sig')
            else:
                text = request['config']
            data = validator()(text).encode()
            if not path.exists():
                existing = list((ROOT / str(uid)).glob('*/*.conf'))
                if len(existing) >= 1024 or sum(p.stat().st_size for p in existing) + len(data) > 64 * 1024 * 1024:
                    raise ValueError('Se alcanzó el límite de almacenamiento de perfiles gestionados para esta cuenta.')
            private_directory(path.parent)
            if path.exists():
                current = read_regular(path)
                if current != data:
                    raise ValueError('Este UUID ya tiene otra configuración; importa una nueva revisión con otro identificador.')
            else:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(data)
            return metadata(path, data)
        if operation == 'cancel' and observation(uid, profile_id)['state'] == 'Desconectado':
            # Comprobar que la interfaz no existe: una interfaz DOWN también debe limpiarse.
            if not Path('/sys/class/net', interface(uid, profile_id)).exists():
                return {'state': 'Desconectado', 'ip_addresses': []}
        data = read_regular(path)
        if operation == 'inspect':
            return metadata(path, data)
        validator()(data.decode())
        if operation == 'connect':
            if request.get('fingerprint') and hashlib.sha256(data).hexdigest() != request['fingerprint']:
                raise ValueError('La revisión registrada no coincide con la biblioteca.')
            if cancellation():
                return observation(uid, profile_id)
            if Path('/sys/class/net', interface(uid, profile_id)).exists():
                raise ValueError('La interfaz ya existe; actualiza su estado.')
            command(['/usr/bin/wg-quick', 'up', str(path)])
            try:
                command(['/usr/sbin/ip', 'link', 'set', 'dev', interface(uid, profile_id), 'alias', f'vpn-manager:{uid}:{profile_id}'])
            except Exception:
                command(['/usr/bin/wg-quick', 'down', str(path)])
                raise
            if cancellation():
                command(['/usr/bin/wg-quick', 'down', str(path)])
        else:
            observation(uid, profile_id)  # Rechaza interfaces ajenas antes de down.
            command(['/usr/bin/wg-quick', 'down', str(path)])
        return observation(uid, profile_id)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1 or not os.environ.get('SUDO_UID', '').isdecimal():
        raise ValueError('El componente sólo admite el protocolo autorizado para el usuario original.')
    uid = int(os.environ['SUDO_UID'])
    if uid == 0:
        raise ValueError('La GUI debe ejecutarse como usuario normal.')
    # Límite suficiente para JSON escapado de un archivo de hasta 2 MiB.
    request = json.loads(sys.stdin.buffer.raw.readline(LIMIT * 6 + 4096))
    return dispatch(uid, request)


if __name__ == '__main__':
    try:
        print(json.dumps({'ok': True, **main()}), flush=True)
    except ValueError as error:
        print(json.dumps({'error': str(error)}), flush=True)
        sys.exit(1)
    except Exception:
        print(json.dumps({'error': 'Operación privilegiada fallida. No se mostraron claves ni datos sensibles.'}), flush=True)
        sys.exit(1)
