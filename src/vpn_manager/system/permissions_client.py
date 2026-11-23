"""Cliente del componente autorizado. Sin contraseñas ni cambios de sudoers aquí."""
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import time

BROKER = Path('/usr/libexec/vpn-manager/wireguard-helper')
MANAGED = Path('/var/lib/vpn-manager/wireguard')
VERSION = 4
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}


def verify_installation():
    try:
        for path in (BROKER.parent, BROKER.parent.parent, BROKER.parent.parent.parent, BROKER):
            info = path.lstat()
            expected = stat.S_ISREG(info.st_mode) if path == BROKER else stat.S_ISDIR(info.st_mode)
            if not expected or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError('El componente WireGuard tiene permisos inseguros; vuelve a habilitarlo desde Configuración.')
    except FileNotFoundError:
        raise ValueError('WireGuard no está habilitado. Abre Configuración → Habilitar WireGuard.') from None


def call(request, cancel_check=None):
    verify_installation()
    # La regla instalada autoriza este único ejecutable SIN argumentos.
    process = subprocess.Popen(['/usr/bin/sudo', '-n', '--', str(BROKER)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
    cancelled = False
    output = bytearray()
    selector = selectors.DefaultSelector()
    try:
        process.stdin.write((json.dumps(request)+'\n').encode())
        process.stdin.flush()
        selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
        selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
        deadline = time.monotonic() + 180
        while selector.get_map() or process.poll() is None:
            if cancel_check and not cancelled and cancel_check():
                cancelled = True
                try:
                    process.stdin.write(b'{"cancel":true}\n')
                    process.stdin.flush()
                except BrokenPipeError:
                    pass
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                elif key.data == 'stdout':
                    output.extend(chunk)
                    if len(output) > 2 * 1024 * 1024:
                        raise ValueError('Respuesta WireGuard demasiado grande.')
                # stderr se descarta: nunca reenviar mensajes potencialmente sensibles.
            if time.monotonic() >= deadline:
                raise ValueError('El componente no respondió a tiempo. Actualiza el estado antes de reintentar.')
        if cancelled:
            return {'_cancel_requested': True}
        try:
            response = json.loads(output)
        except (ValueError, UnicodeError):
            response = {}
        if not isinstance(response, dict) or process.returncode or not response.get('ok'):
            message = response.get('error') if isinstance(response, dict) else None
            raise ValueError(message or 'Falta autorización permanente para WireGuard. Abre Configuración → Habilitar WireGuard.')
        return response
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()


def readiness():
    try:
        response = call({'operation': 'probe'})
        if response.get('version') != VERSION or response.get('setup_version') != VERSION or response.get('uid') != os.getuid():
            return {'ready': False, 'message': 'La habilitación necesita actualizarse para esta cuenta.'}
        return {'ready': True, 'message': 'WireGuard habilitado: no se pedirá contraseña administrativa por conexión.'}
    except (ValueError, OSError) as error:
        required = ('/usr/bin/sudo', '/usr/sbin/visudo', '/usr/bin/pkexec', '/usr/bin/wg-quick', '/usr/sbin/ip')
        missing = [Path(path).name for path in required if not Path(path).is_file()]
        if missing:
            return {'ready': False, 'can_enable': False, 'message': 'Faltan componentes del sistema: ' + ', '.join(missing)}
        return {'ready': False, 'can_enable': True, 'message': str(error) if isinstance(error, ValueError) else 'No se pudo consultar la habilitación WireGuard.'}
