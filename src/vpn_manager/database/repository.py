"""Biblioteca SQLite local; los originales sólo se referencian por ruta."""
import os
from pathlib import Path
import sqlite3
from uuid import uuid4
from vpn_manager.core.models import Profile, Protocol


class ProfileRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Crear con permisos restrictivos desde el primer instante.
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        self.connection = sqlite3.connect(path)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, protocol TEXT NOT NULL,
            comment TEXT NOT NULL, favorite INTEGER NOT NULL,
            config_path TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL UNIQUE
        )""")
        self.connection.commit()

    def list(self) -> tuple[Profile, ...]:
        rows = self.connection.execute(
            "SELECT id, name, protocol, comment, favorite, config_path, fingerprint FROM profiles ORDER BY rowid"
        )
        return tuple(Profile(id=r[0], name=r[1], protocol=Protocol(r[2]), comment=r[3],
                             favorite=bool(r[4]), config_path=r[5], fingerprint=r[6]) for r in rows)

    def add(self, profile: Profile) -> None:
        try:
            with self.connection:
                self.connection.execute("INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?)", (
                    profile.id, profile.name, profile.protocol.value, profile.comment,
                    int(profile.favorite), profile.config_path, profile.fingerprint,
                ))
        except sqlite3.IntegrityError:
            raise ValueError("Este archivo o su contenido ya están registrados.") from None

    def discover_wireguard(self, entries):
        """Añadir perfiles del sistema sin duplicar ni perder metadatos del usuario."""
        profiles = self.list()
        paths = {p.config_path for p in profiles}
        fingerprints = {p.fingerprint for p in profiles}
        for entry in entries:
            path = Path(entry['path'])
            fingerprint = entry['fingerprint']
            if path.parent != Path('/etc/wireguard') or path.suffix != '.conf':
                continue
            if str(path) in paths or fingerprint in fingerprints:
                continue
            self.add(Profile(str(uuid4()), path.stem, Protocol.WIREGUARD,
                             config_path=str(path), fingerprint=fingerprint))
            paths.add(str(path))
            fingerprints.add(fingerprint)

    def update(self, profile: Profile) -> None:
        with self.connection:
            self.connection.execute("UPDATE profiles SET name=?, comment=?, favorite=? WHERE id=?", (
                profile.name, profile.comment, int(profile.favorite), profile.id,
            ))

    def relocate(self, profile: Profile) -> None:
        """Cambiar referencia conservando UUID y metadatos, sin tocar archivos."""
        try:
            with self.connection:
                self.connection.execute(
                    "UPDATE profiles SET name=?, comment=?, favorite=?, config_path=?, fingerprint=? WHERE id=?",
                    (profile.name, profile.comment, int(profile.favorite), profile.config_path, profile.fingerprint, profile.id))
        except sqlite3.IntegrityError:
            raise ValueError("Este perfil de /etc/wireguard ya está registrado.") from None

    def remove(self, profile_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM profiles WHERE id=?", (profile_id,))

    def close(self) -> None:
        self.connection.close()
