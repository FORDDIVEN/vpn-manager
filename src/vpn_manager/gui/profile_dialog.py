"""Edición de metadatos y selección del archivo original, sin modificarlo."""
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QMessageBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
)
from vpn_manager.core.models import Profile, Protocol
from vpn_manager.core.profile_manager import import_profile
from vpn_manager.core.connection_manager import WORKER


class ProfileDialog(QDialog):
    def __init__(self, protocol: Protocol, profile: Profile | None = None, parent=None, *, copy_to_system=False):
        super().__init__(parent)
        self.protocol = protocol
        self.editing = profile is not None and not copy_to_system
        self.original_profile = profile if copy_to_system else None
        self.imported_profile = None
        self.task = None
        self.reply = None
        self.process = None
        self.pending_profile = None
        self.setWindowTitle(f"{'Editar' if profile else 'Importar'} perfil {protocol.value}")
        self.resize(420, 330)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        form.addRow("Protocolo", QLabel(protocol.value))
        self.source = QComboBox()
        self.source.addItems(["Importar archivo a /etc/wireguard", "Usar perfil existente de /etc/wireguard", "Usar archivo local (sin copiar)"])
        if copy_to_system:
            self.source.setCurrentIndex(0)
        self.system_file = QComboBox()
        self.system_file.setPlaceholderText("Selecciona un perfil del sistema")
        if protocol == Protocol.WIREGUARD and not self.editing:
            form.addRow("Origen", self.source)
            form.addRow("Perfil del sistema", self.system_file)
        self.system_file.hide()
        self.path = QLineEdit(profile.config_path if profile else "")
        self.path.setReadOnly(True)
        self.path.setPlaceholderText("Seleccionar archivo original…")
        path_row = QHBoxLayout()
        path_row.addWidget(self.path)
        if not self.editing:
            self.browse = QPushButton("…")
            browse = self.browse
            browse.setFixedWidth(30)
            browse.setToolTip("Seleccionar archivo VPN")
            browse.clicked.connect(lambda: self.select_file(protocol))
            path_row.addWidget(browse)
        form.addRow("Archivo", path_row)
        self.name = QLineEdit(profile.name if profile else "")
        self.name.setMaxLength(200)
        form.addRow("Nombre", self.name)
        self.comment = QPlainTextEdit(profile.comment if profile else "")
        self.comment.setPlaceholderText("¿A qué pertenece esta VPN? Evita escribir secretos.")
        self.comment.setMaximumHeight(90)
        form.addRow("Comentario", self.comment)
        self.favorite = QCheckBox("Favorito")
        self.favorite.setChecked(profile.favorite if profile else False)
        form.addRow(self.favorite)
        notice = QLabel(
            "Habilita WireGuard una vez desde Configuración para gestionar conexiones. "
            "Puedes copiar el perfil a /etc/wireguard o guardar sólo su referencia local. El archivo original se conserva."
            if protocol == Protocol.WIREGUARD and not self.editing else
            "Sólo se editan metadatos. El archivo original no se modifica.")
        notice.setWordWrap(True)
        notice.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(notice)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.source.currentIndexChanged.connect(self.select_source)
        self.system_file.currentIndexChanged.connect(self.select_system_file)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.timeout_task)
        self.name.textChanged.connect(self.validate)
        self.path.textChanged.connect(self.validate)
        self.comment.textChanged.connect(self.validate)
        self.validate()

    def validate(self, *_args):
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(
            not self.task and bool(self.path.text() and self.name.text().strip())
            and len(self.comment.toPlainText()) <= 4000)

    def select_source(self, index):
        system = index == 1
        self.system_file.setVisible(system)
        self.browse.setEnabled(not system)
        self.path.clear()
        if system:
            self.start_task('wg-list', Profile(str(uuid4()), '', Protocol.WIREGUARD))

    def select_system_file(self, index):
        metadata = self.system_file.itemData(index)
        self.path.setText(metadata['path'] if metadata else '')
        if metadata and not self.name.text():
            self.name.setText(Path(metadata['path']).stem)

    def save(self):
        if self.protocol != Protocol.WIREGUARD or self.editing:
            self.accept()
            return
        try:
            if self.source.currentIndex() == 1:
                metadata = self.system_file.currentData()
                if not metadata:
                    return
                candidate = Profile(str(uuid4()), self.name.text().strip(), Protocol.WIREGUARD,
                                    self.comment.toPlainText().strip(), favorite=self.favorite.isChecked(),
                                    config_path=metadata['path'], fingerprint=metadata['fingerprint'])
            else:
                candidate = import_profile(self.path.text(), Protocol.WIREGUARD, self.name.text(),
                                           self.comment.toPlainText(), self.favorite.isChecked())
            if self.original_profile:
                candidate = replace(candidate, id=self.original_profile.id)
            self.pending_profile = candidate
            if self.source.currentIndex() == 2:
                self.imported_profile = candidate
                self.accept()
                return
            self.start_task('wg-import', candidate)
        except (ValueError, OSError) as error:
            message = str(error) if isinstance(error, ValueError) else 'No se pudo leer el archivo seleccionado.'
            QMessageBox.warning(self, 'No se pudo importar', message)

    def start_task(self, task, profile):
        self.task, self.reply = task, None
        self.source.setEnabled(False)
        self.system_file.setEnabled(False)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(False)
        self.validate()
        self.process = QProcess(self)
        self.process.setProgram('/usr/bin/python3')
        self.process.setArguments(['-I', str(WORKER)])
        request = {'operation': task, 'profile': {'id': profile.id, 'path': profile.config_path,
                   'protocol': profile.protocol.value, 'fingerprint': profile.fingerprint}}
        self.process.started.connect(lambda: self.process.write((json.dumps(request)+'\n').encode()))
        self.process.finished.connect(self.finish_task)
        self.process.errorOccurred.connect(self.task_error)
        self.timeout.start(240000)
        self.process.start()

    def task_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.finish_task(-1)

    def timeout_task(self):
        if self.task:
            self.process.kill()

    def finish_task(self, code, *_args):
        if not self.task:
            return
        task, self.task = self.task, None
        self.timeout.stop()
        # No mostrar stderr de herramientas o perfiles.
        self.process.readAllStandardError()
        try:
            reply = json.loads(bytes(self.process.readAllStandardOutput()).decode())
        except (ValueError, UnicodeError):
            reply = {}
        if not isinstance(reply, dict):
            reply = {}
        self.process.deleteLater()
        self.source.setEnabled(True)
        self.system_file.setEnabled(True)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(True)
        if code or reply.get('event') != 'result':
            QMessageBox.warning(self, 'WireGuard', reply.get('message', 'No se pudo completar el acceso administrativo a /etc/wireguard.'))
            self.validate()
            return
        if task == 'wg-list':
            self.system_file.clear()
            for metadata in reply.get('profiles', []):
                self.system_file.addItem(metadata['filename'], metadata)
            if self.system_file.count():
                self.system_file.setCurrentIndex(0)
            self.select_system_file(self.system_file.currentIndex())
            if not reply.get('profiles') or reply.get('rejected'):
                QMessageBox.information(self, 'Perfiles WireGuard',
                    f"Disponibles: {len(reply.get('profiles', []))}. Omitidos por permisos, formato u opciones no admitidas: {reply.get('rejected', 0)}.")
        else:
            self.imported_profile = replace(self.pending_profile, config_path=reply['path'], fingerprint=reply['fingerprint'])
            self.accept()
        self.validate()

    def reject(self):
        if not self.task:
            super().reject()

    def closeEvent(self, event):
        if self.task:
            event.ignore()
        else:
            super().closeEvent(event)

    def select_file(self, protocol: Protocol):
        pattern = "OpenVPN (*.ovpn);;Todos los archivos (*)" if protocol == Protocol.OPENVPN else "WireGuard (*.conf);;Todos los archivos (*)"
        path, _ = QFileDialog.getOpenFileName(self, f"Importar {protocol.value}", "", pattern)
        if path:
            self.path.setText(path)
            if not self.name.text():
                self.name.setText(Path(path).stem)
