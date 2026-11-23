"""Validación local de configuraciones importadas; no realiza operaciones privilegiadas."""
import base64
import ipaddress
import re

LIMIT = 2 * 1024 * 1024


def key_value(value):
    try:
        if len(base64.b64decode(value, validate=True)) != 32:
            raise ValueError()
    except Exception:
        raise ValueError('Clave WireGuard inválida (se requieren 32 bytes en base64).') from None
    return value


def number(value, maximum, minimum=0):
    if not value.isdecimal() or not minimum <= int(value) <= maximum:
        raise ValueError('Valor numérico WireGuard fuera de rango.')
    return str(int(value))


def normalize(text):
    """Lista permitida y reconstrucción; nunca pasar el texto original a wg-quick."""
    if len(text.encode()) > LIMIT or '\x00' in text:
        raise ValueError('Configuración demasiado grande o inválida.')
    output, section, seen = [], None, set()
    interfaces, peers = 0, 0
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line or line.startswith(';'):
            continue
        if line.casefold() in ('[interface]', '[peer]'):
            line = '[Interface]' if line.casefold() == '[interface]' else '[Peer]'
            if section is not None:
                required = 'privatekey' if section == '[Interface]' else 'publickey'
                if required not in seen:
                    raise ValueError('Falta una clave obligatoria WireGuard.')
            section, seen = line, set()
            if line == '[Interface]':
                interfaces += 1
                if interfaces != 1 or peers:
                    raise ValueError('Se requiere una única sección Interface inicial.')
            else:
                peers += 1
                if interfaces != 1:
                    raise ValueError('Peer requiere una sección Interface previa.')
            output.append(line)
            continue
        if not section or '=' not in line:
            raise ValueError('Sintaxis WireGuard no admitida.')
        key, value = (part.strip() for part in line.split('=', 1))
        lower = key.lower()
        interface_keys = {'privatekey', 'address', 'dns', 'mtu', 'listenport', 'table', 'fwmark'}
        peer_keys = {'publickey', 'presharedkey', 'allowedips', 'endpoint', 'persistentkeepalive'}
        if lower not in (interface_keys if section == '[Interface]' else peer_keys):
            raise ValueError('Opción WireGuard no admitida. Hooks y SaveConfig no están permitidos.')
        if lower in seen:
            raise ValueError('Opciones repetidas no admitidas; combina sus valores en una línea.')
        seen.add(lower)
        if lower in ('privatekey', 'publickey', 'presharedkey'):
            value = key_value(value)
        elif lower in ('address', 'allowedips'):
            parts = [p.strip() for p in value.split(',')]
            if any('%' in p for p in parts):
                raise ValueError('No se admiten identificadores de zona en direcciones WireGuard.')
            try:
                value = ', '.join(str(ipaddress.ip_interface(p) if lower == 'address'
                                      else ipaddress.ip_network(p, strict=False)) for p in parts)
            except ValueError:
                raise ValueError('Dirección o red WireGuard inválida.') from None
        elif lower == 'dns':
            parts = [p.strip() for p in value.split(',')]
            for part in parts:
                try:
                    ipaddress.ip_address(part)
                except ValueError:
                    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', part):
                        raise ValueError('DNS o dominio de búsqueda inválido.') from None
            value = ', '.join(parts)
        elif lower == 'endpoint':
            match = re.fullmatch(r'(\[[0-9a-fA-F:]+\]|[A-Za-z0-9][A-Za-z0-9.-]{0,252}):([0-9]{1,5})', value)
            if not match:
                raise ValueError('Endpoint WireGuard inválido.')
            number(match[2], 65535, 1)
            if match[1].startswith('['):
                ipaddress.IPv6Address(match[1][1:-1])
        elif lower == 'table':
            if value not in ('auto', 'off'):
                value = number(value, 4294967295, 1)
        else:
            maximum = 65535 if lower in ('listenport', 'persistentkeepalive', 'mtu') else 4294967295
            value = number(value, maximum, 576 if lower == 'mtu' else 0)
        canonical = {'privatekey': 'PrivateKey', 'publickey': 'PublicKey', 'presharedkey': 'PresharedKey',
                     'address': 'Address', 'dns': 'DNS', 'mtu': 'MTU', 'listenport': 'ListenPort',
                     'table': 'Table', 'fwmark': 'FwMark', 'allowedips': 'AllowedIPs',
                     'endpoint': 'Endpoint', 'persistentkeepalive': 'PersistentKeepalive'}[lower]
        output.append(f'{canonical} = {value}')
    if interfaces != 1 or not peers or 'publickey' not in seen:
        raise ValueError('Se requieren Interface con PrivateKey y Peer con PublicKey.')
    return '\n'.join(output) + '\n'

