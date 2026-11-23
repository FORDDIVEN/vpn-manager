"""Trabajador sin privilegios: JSON por stdin/stdout; nunca imprime secretos.

Se ejecuta con /usr/bin/python3 para acceder al binding D-Bus de OpenVPN 3
instalado por la distribución, sin contaminar el entorno virtual de la GUI.
"""
import contextlib
import hashlib
import io
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import select
import shlex
import subprocess
import sys
import stat
import time
from uuid import UUID

LIMIT = 2 * 1024 * 1024
SYSTEM_CONFIGS = Path('/etc/wireguard')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}


class Cancelled(Exception):
    """Cancelación cooperativa: el propietario de la operación realiza la limpieza."""


def input_stream():
    # Evitar que readline adelante una segunda orden y oculte el cancel a select.
    return getattr(getattr(sys.stdin, 'buffer', None), 'raw', sys.stdin)


def check_cancel():
    stream = input_stream()
    if select.select([stream], [], [], 0)[0]:
        line = stream.readline()
        if not line or json.loads(line).get('cancel'):
            raise Cancelled()


def emit(event):
    print(json.dumps(event), flush=True)


def read_profile(profile):
    path = Path(profile['path']).resolve(strict=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('La configuración debe ser un archivo regular.')
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != profile['fingerprint']:
        raise ValueError('El archivo cambió desde la importación. Vuelve a importarlo antes de conectar.')
    return path, data.decode('utf-8-sig')


def run(arguments, *, input=None, timeout=15):
    try:
        result = subprocess.run(arguments, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, env=ENV, check=False)
    except FileNotFoundError:
        raise ValueError('Falta una herramienta requerida del sistema.') from None
    except subprocess.TimeoutExpired:
        raise ValueError('La operación agotó el tiempo de espera. Actualiza el estado antes de reintentar.') from None
    return result


def interface_data(interface, wireguard=False):
    result = run(['/usr/sbin/ip', '-details', '-json', 'address', 'show', 'dev', interface])
    if result.returncode:
        if not Path("/sys/class/net", interface).exists():
            return None
        raise ValueError("No se pudo observar la interfaz de red existente.")
    devices = json.loads(result.stdout)
    if not devices:
        return None
    device = devices[0]
    if wireguard and device.get('linkinfo', {}).get('info_kind') != 'wireguard':
        raise ValueError('El nombre de interfaz está ocupado por otro tipo de dispositivo.')
    addresses = [str(ipaddress.ip_address(a['local'])) for a in device.get('addr_info', []) if a.get('local')]
    return {'interface': interface, 'ip_addresses': addresses, 'up': 'UP' in device.get('flags', []), 'alias': device.get('ifalias', '')}


def openvpn_name(profile):
    return f"vpn-manager:{os.getuid()}:{profile['id']}:"


def owned_sessions(manager, profile):
    prefix = openvpn_name(profile)
    return [session for session in manager.FetchAvailableSessions()
            if int(session.GetProperty('owner')) == os.getuid()
            and str(session.GetProperty('config_name')).startswith(prefix)]


def ovpn_snapshot(manager, profile):
    sessions = owned_sessions(manager, profile)
    if not sessions:
        return {'state': 'Desconectado', 'ip_addresses': []}
    if len(sessions) != 1:
        raise ValueError('Hay varias sesiones de este perfil. Revísalas con openvpn3 antes de continuar.')
    session = sessions[0]
    status = session.GetStatus()
    minor = int(status['minor'].value)
    major = int(status['major'].value)
    states = {5: 'Conectando', 6: 'Conectando', 7: 'Conectado', 8: 'Desconectando',
              9: 'Desconectado', 10: 'Error', 11: 'Error', 12: 'Conectando',
              13: 'Desconectando', 14: 'Desconectado', 15: 'Conectando',
              16: 'Desconectado', 17: 'Conectando', 18: 'Desconectado', 19: 'Desconectado',
              20: 'Conectando', 21: 'Conectando', 22: 'Error'}
    state = 'Error' if major == 1 else states.get(minor, 'Desconocido')
    snapshot = {'state': state, 'session_path': str(session.GetPath()), 'ip_addresses': []}
    if state == 'Error':
        snapshot['error'] = 'Falló la autenticación OpenVPN 3.' if minor == 11 else 'OpenVPN 3 informó un fallo; revisa credenciales y compatibilidad del perfil.'
    if state == 'Conectado':
        device = str(session.GetProperty('device_name'))
        if device:
            snapshot.update(interface_data(device) or {})
    return snapshot


def credentials(session):
    for slot in session.FetchUserInputSlots():
        _, group = slot.GetTypeGroup()
        if int(group.value) not in (1, 2, 3, 4, 5):
            raise ValueError('Este método de autenticación requiere un flujo externo aún no admitido.')
        # Etiquetas fijas: no reenviar mensajes arbitrarios del servidor a los logs/UI.
        secret = bool(slot.GetInputMask())
        label = 'Contraseña / código de autenticación' if secret else 'Usuario / respuesta de autenticación'
        emit({'event': 'credential', 'label': label, 'secret': secret})
        answer = json.loads(input_stream().readline())
        if answer.get('cancel'):
            raise Cancelled()
        slot.ProvideInput(answer['value'])


def openvpn_operation(operation, profile):
    try:
        import dbus
        import openvpn3
    except ImportError:
        raise ValueError('Falta el binding Python del sistema para OpenVPN 3 (openvpn3 y python3-dbus).') from None
    manager = openvpn3.SessionManager(dbus.SystemBus())
    if operation == 'status':
        return ovpn_snapshot(manager, profile)
    existing = owned_sessions(manager, profile)
    if operation in ('disconnect', 'cancel'):
        if operation == 'cancel' and not existing:
            return ovpn_snapshot(manager, profile)
        if len(existing) != 1:
            raise ValueError('No hay una única sesión propia para desconectar; actualiza el estado.')
        existing[0].Disconnect()
        return ovpn_snapshot(manager, profile)
    if existing:
        raise ValueError('Este perfil ya tiene una sesión. Desconéctala antes de iniciar otra.')
    check_cancel()
    path, text = read_profile(profile)
    # El parser oficial combina certificados externos. Las inclusiones y ejecución
    # de scripts se rechazan antes de invocarlo, incluso si OpenVPN 3 las ignora.
    block = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('<'):
            if line.startswith('</'):
                block = None
            else:
                block = line
            continue
        if block:
            continue
        tokens = shlex.split(line, comments=True)
        if tokens and tokens[0].lstrip('-') in {
            'config', 'cd', 'up', 'down', 'route-up', 'route-pre-down', 'ipchange',
            'plugin', 'script-security', 'tls-verify', 'auth-user-pass-verify', 'client-connect', 'client-disconnect',
        }:
            raise ValueError('El perfil usa inclusiones, cambios de directorio o scripts no admitidos.')
    os.chdir(path.parent)
    try:
        # Capturar mensajes del parser para evitar volcar líneas con credenciales.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            descriptor = os.memfd_create('vpn-manager-profile', os.MFD_CLOEXEC)
            try:
                os.write(descriptor, text.encode())
                parser = openvpn3.ConfigParser(['vpn-manager', '--config', f'/proc/self/fd/{descriptor}'], 'VPN Manager')
                config_text = parser.GenerateConfig()
            finally:
                os.close(descriptor)
    except Exception:
        raise ValueError('OpenVPN 3 no pudo procesar el perfil o sus archivos externos.') from None
    configs = openvpn3.ConfigurationManager(dbus.SystemBus())
    check_cancel()
    config = configs.Import(openvpn_name(profile) + profile['fingerprint'], config_text, True, False)
    session = None
    try:
        check_cancel()
        session = manager.NewTunnel(config)
        deadline = time.monotonic() + 120
        connected_requested = False
        while time.monotonic() < deadline:
            check_cancel()
            credentials(session)
            status = session.GetStatus()
            minor = int(status['minor'].value)
            if minor == 7:
                return ovpn_snapshot(manager, profile)
            if minor in (10, 11, 22):
                raise ValueError('OpenVPN 3 rechazó la conexión o requiere autenticación web no admitida.')
            if not connected_requested:
                session.Ready()
                session.Connect()
                connected_requested = True
            time.sleep(0.5)
        raise ValueError('OpenVPN 3 no completó la conexión en 120 segundos.')
    except Exception:
        if session:
            try:
                session.Disconnect()
            except Exception:
                pass
        raise
    finally:
        try:
            config.Remove()
        except Exception:
            pass  # Single-use: el servicio puede haber retirado ya la configuración.


def permissions_client():
    spec = importlib.util.spec_from_file_location('permissions_client', Path(__file__).with_name('permissions_client.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def broker_request(request, cancellable=False):
    def cancelled():
        try:
            check_cancel()
        except Cancelled:
            return True
        return False
    response = permissions_client().call(request, cancel_check=cancelled if cancellable else None)
    if response.get('_cancel_requested'):
        raise Cancelled()
    return response


def managed_profile(profile):
    path = Path(profile['path'])
    root = Path('/var/lib/vpn-manager/wireguard')
    if path.is_relative_to(root):
        return broker_request({'operation': 'inspect', 'id': profile['id']})
    if path.parent == SYSTEM_CONFIGS:
        return broker_request({'operation': 'register-system', 'id': profile['id'],
                               'filename': path.name, 'fingerprint': profile['fingerprint']})
    _, text = read_profile(profile)
    return broker_request({'operation': 'register', 'id': profile['id'], 'config': text})


def wireguard_library(operation, profile):
    if operation == 'wg-list':
        return broker_request({'operation': 'list'})
    path = Path(profile['path'])
    if path.parent == SYSTEM_CONFIGS:
        result = broker_request({'operation': 'list'})
        for metadata in result.get('profiles', []):
            if metadata['path'] == str(path) and metadata['fingerprint'] == profile['fingerprint']:
                return metadata
        raise ValueError('El perfil del sistema cambió o no está disponible; actualiza el listado.')
    _, text = read_profile(profile)
    import re
    stem = path.stem
    if not re.fullmatch(r'[A-Za-z0-9_=+.-]{1,15}', stem):
        stem = 'vpn' + profile['id'].replace('-', '')[:12]
    return broker_request({'operation': 'publish-system', 'filename': stem + '.conf', 'config': text})


def wg_operation(operation, profile):
    if operation == 'connect':
        check_cancel()
        metadata = managed_profile(profile)
        check_cancel()
        return broker_request({'operation': 'connect', 'id': profile['id'],
                               'fingerprint': metadata['fingerprint']}, cancellable=True)
    return broker_request({'operation': operation, 'id': profile['id']})


def main():
    request = json.loads(input_stream().readline(LIMIT + 4096))
    operation, profile = request['operation'], request['profile']
    if operation not in ('connect', 'disconnect', 'cancel', 'status', 'wg-list', 'wg-import', 'permissions-status') or str(UUID(profile['id'])) != profile['id']:
        raise ValueError('Solicitud de backend inválida.')
    if operation == 'permissions-status':
        emit({'event': 'result', **permissions_client().readiness()})
        return
    if operation in ('wg-list', 'wg-import'):
        emit({'event': 'result', **wireguard_library(operation, profile)})
        return
    backend = {'OpenVPN': openvpn_operation, 'WireGuard': wg_operation}.get(profile['protocol'])
    if backend is None:
        raise ValueError('Protocolo no admitido.')
    try:
        snapshot = backend(operation, profile)
        if operation == 'connect':
            check_cancel()
    except Cancelled:
        snapshot = backend('cancel', profile)
    emit({'event': 'result', **snapshot})


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        emit({'event': 'error', 'message': str(error)})
        sys.exit(1)
    except Exception:
        # D-Bus y herramientas pueden incluir datos del perfil en sus excepciones.
        emit({'event': 'error', 'message': 'No se pudo consultar o controlar el servicio VPN. Comprueba D-Bus, permisos y dependencias.'})
        sys.exit(1)
