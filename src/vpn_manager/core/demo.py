"""Backend de demostración en memoria. No ejecuta procesos ni accede a la red."""
from dataclasses import replace
from .models import Profile, Protocol, Session, State


class DemoBackend:
    def __init__(self, profiles: tuple[Profile, ...] | None = None) -> None:
        self.profiles = (
            Profile("office", "Oficina · ejemplo", Protocol.OPENVPN, "Acceso a la red de la empresa", ("oficina",), True),
            Profile("lab", "Laboratorio · ejemplo", Protocol.WIREGUARD, "Entorno de pruebas y desarrollo", ("desarrollo",)),
            Profile("home", "Casa · ejemplo", Protocol.WIREGUARD, "Acceso a los equipos de casa", ("hogar",), True),
            Profile("backup", "Respaldo · ejemplo", Protocol.OPENVPN, "Conexión alternativa a la empresa"),
        )
        if profiles is not None:
            self.profiles = profiles
        self.sessions = {p.id: Session(p.id) for p in self.profiles}
        self.logs: list[tuple[str, str]] = []

    def begin(self, profile_id: str) -> bool:
        session = self.sessions[profile_id]
        if session.state in (State.CONNECTING, State.DISCONNECTING):
            return False
        target = State.DISCONNECTING if session.state == State.CONNECTED else State.CONNECTING
        self.sessions[profile_id] = replace(session, state=target)
        self.logs.append((profile_id, f"SIMULACIÓN: {target.value}"))
        return True

    def complete(self, profile_id: str) -> None:
        session = self.sessions[profile_id]
        transitions = {State.CONNECTING: State.CONNECTED, State.DISCONNECTING: State.DISCONNECTED}
        if session.state not in transitions:
            return
        target = transitions[session.state]
        self.sessions[profile_id] = replace(session, state=target)
        self.logs.append((profile_id, f"SIMULACIÓN: {target.value}"))

    def reset(self) -> None:
        self.sessions = {p.id: Session(p.id) for p in self.profiles}
        self.logs.clear()
