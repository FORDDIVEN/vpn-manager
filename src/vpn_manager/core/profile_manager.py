"""Reconocimiento básico para importar referencias; no autoriza ejecutar perfiles."""
import hashlib
import os
from pathlib import Path
import re
import stat
from uuid import uuid4
from .models import Profile, Protocol

MAX_PROFILE_SIZE = 2 * 1024 * 1024


def import_profile(path: str, expected: Protocol, name: str, comment: str,
                   favorite: bool = False) -> Profile:
    name = name.strip()
    if not name or len(name) > 200 or len(comment) > 4000:
        raise ValueError("Indica un nombre de hasta 200 caracteres y un comentario de hasta 4000.")
    source = Path(path).expanduser().resolve(strict=True)
    # O_NONBLOCK evita bloquear la GUI si se selecciona un FIFO por accidente.
    descriptor = os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Selecciona un archivo de configuración regular.")
        data = stream.read(MAX_PROFILE_SIZE + 1)
    if len(data) > MAX_PROFILE_SIZE:
        raise ValueError("La configuración supera el límite de 2 MiB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("La configuración debe ser un archivo de texto UTF-8.") from None
    if "\x00" in text:
        raise ValueError("El archivo no es una configuración de texto válida.")
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith(("#", ";"))]
    sections = {line.split("#", 1)[0].strip().casefold() for line in lines}
    is_wg = "[interface]" in sections and "[peer]" in sections
    # Excluir bloques inline: su contenido puede parecer una directiva.
    directives = []
    block = None
    for line in lines:
        if line.startswith("<"):
            if line.startswith("</"):
                block = None
            else:
                block = line
            continue
        if block is None:
            directives.append(line)
    is_ovpn = any(re.match(r"^(?:--)?(?:client|remote|dev|tls-client)(?:\s|$)", line)
                  for line in directives)
    if is_wg and not is_ovpn:
        detected = Protocol.WIREGUARD
    elif is_ovpn and not is_wg:
        detected = Protocol.OPENVPN
    else:
        raise ValueError("No se reconoce un perfil OpenVPN o WireGuard inequívoco.")
    if detected != expected:
        raise ValueError(f"El archivo parece ser {detected.value}. Usa su pestaña para importarlo.")
    return Profile(str(uuid4()), name, detected, comment.strip(), favorite=favorite,
                   config_path=str(source), fingerprint=hashlib.sha256(data).hexdigest())
