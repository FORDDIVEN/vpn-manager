"""Modelos del prototipo; ninguna configuración ni secreto se almacena aquí."""
from dataclasses import dataclass
from enum import StrEnum


class Protocol(StrEnum):
    OPENVPN = "OpenVPN"
    WIREGUARD = "WireGuard"


class State(StrEnum):
    DISCONNECTED = "Desconectado"
    CONNECTING = "Conectando"
    CONNECTED = "Conectado"
    DISCONNECTING = "Desconectando"
    ERROR = "Error"
    UNKNOWN = "Desconocido"


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    protocol: Protocol
    comment: str = ""
    tags: tuple[str, ...] = ()
    favorite: bool = False
    config_path: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class Session:
    profile_id: str
    state: State = State.DISCONNECTED
    simulated: bool = True
    ip_addresses: tuple[str, ...] = ()
    interface: str = ""
    last_error: str = ""


def matches(profile: Profile, session: Session, *, query: str = "",
            protocol: str = "", state: str = "",
            favorites_only: bool = False) -> bool:
    searchable = " ".join((profile.name, profile.comment, *profile.tags)).casefold()
    return (query.strip().casefold() in searchable
            and (not protocol or profile.protocol == protocol)
            and (not state or session.state == state)
            and (not favorites_only or profile.favorite))
