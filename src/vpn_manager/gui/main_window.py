"""Biblioteca de perfiles y control asíncrono de OpenVPN 3 y WireGuard."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import json
import ipaddress
from uuid import uuid4

from PySide6.QtCore import QSettings, QStandardPaths, QTimer, QProcess
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QMenu, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QInputDialog, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QScrollArea, QFrame,
    QTabBar, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from vpn_manager.core.connection_manager import ConnectionManager, WORKER
from vpn_manager.core.models import Protocol, State, matches
from vpn_manager.core.profile_manager import import_profile
from vpn_manager.database.repository import ProfileRepository
from vpn_manager.gui.profile_dialog import ProfileDialog
from vpn_manager.gui.permissions_dialog import PermissionsDialog


class MainWindow(QMainWindow):
    def __init__(self, database_path: Path | None = None, *, backend=None, preferences=None) -> None:
        super().__init__()
        if database_path is None:
            database_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) / "vpn-manager" / "profiles.sqlite3"
        self.close_to_tray = False
        self.quit_requested = False
        self.wireguard_scan = None
        self.repository = ProfileRepository(database_path)
        self.backend = backend if backend is not None else ConnectionManager(self.repository.list(), self)
        self.preferences = preferences if preferences is not None else QSettings('VPN Manager', 'VPN Manager')
        self.setWindowTitle("VPN Manager")
        self.resize(820, 400)
        self.setMinimumSize(0, 0)
        root = QWidget()
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setWidget(root)
        self.setCentralWidget(self.content_scroll)
        outer = QVBoxLayout(root)
        banner = QLabel("OpenVPN 3 · WireGuard · Estado del sistema")
        banner.setWordWrap(True)
        banner.setStyleSheet("background: #fff0c2; color: #503800; padding: 6px; font-weight: bold;")
        outer.addWidget(banner)
        body = QHBoxLayout()
        outer.addLayout(body)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        # Panel independiente a la izquierda del contenido, sin superposición.
        self.nav = QListWidget()
        self.nav.setFixedWidth(max(112, self.fontMetrics().horizontalAdvance("Configuración") + 20))
        body.insertWidget(0, self.nav)
        self.nav.setAccessibleName("Menú de navegación")
        self.nav.addItems(["Dashboard", "Conexiones", "Favoritos", "Logs", "Configuración"])
        self.nav.setStyleSheet("QListWidget::item { padding: 8px 6px; }")
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        layout.addWidget(QLabel("<h3>Resumen de la biblioteca</h3>"))
        self.summary = QLabel()
        layout.addWidget(self.summary)
        layout.addWidget(QLabel("OpenVPN 3: estado observado mediante D-Bus.\n"
                                "WireGuard: interfaz configurada y activa; no garantiza respuesta del peer."))
        layout.addStretch()
        self.pages.addWidget(dashboard)
        profiles = QWidget()
        layout = QVBoxLayout(profiles)
        self.title = QLabel()
        layout.addWidget(self.title)
        self.protocol_tabs = QTabBar()
        self.protocol_tabs.setExpanding(False)
        self.protocol_tabs.setAccessibleName("Protocolo VPN")
        for value in Protocol:
            index = self.protocol_tabs.addTab(value.value)
            self.protocol_tabs.setTabData(index, value.value)
        protocol_row = QHBoxLayout()
        protocol_row.addWidget(self.protocol_tabs)
        protocol_row.addStretch()
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(30, 28)
        self.add_button.setToolTip("Agregar perfil VPN")
        self.add_button.setAccessibleName("Agregar perfil VPN: elegir protocolo")
        self.add_menu = QMenu(self.add_button)
        for protocol in Protocol:
            action = self.add_menu.addAction(protocol.value)
            action.triggered.connect(lambda checked=False, p=protocol: self.add_profile(p))
        self.add_button.setMenu(self.add_menu)
        self.add_button.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0px; }")
        protocol_row.addWidget(self.add_button)
        layout.addLayout(protocol_row)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar nombre, comentario o etiqueta…")
        layout.addWidget(self.search)
        self.favorites = QCheckBox("Solo favoritos")
        layout.addWidget(self.favorites)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Perfil", "Protocolo", "Comentario", "Estado", "IP VPN", "Acción", "Detalle"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # El protocolo ya está en las pestañas; el comentario identifica cada VPN.
        self.table.setColumnHidden(1, True)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        # Todas las columnas visibles se ajustan arrastrando el borde del encabezado.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(28)
        widths = {0: 160, 2: max(110, self.fontMetrics().horizontalAdvance("Comentario") + 16),
                  3: self.fontMetrics().horizontalAdvance("Desconectado") + 20,
                  4: 120, 5: self.fontMetrics().horizontalAdvance("Desconectar") + 32, 6: 32}
        for column, width in widths.items():
            self.table.setColumnWidth(column, width)
        self.table.setHorizontalHeaderItem(3, QTableWidgetItem("Estado"))
        self.table.horizontalHeaderItem(4).setToolTip("Dirección asignada a la interfaz VPN durante una sesión real")
        self.table.setHorizontalHeaderItem(6, QTableWidgetItem("⋯"))
        self.table.horizontalHeaderItem(6).setToolTip("Información del perfil")
        layout.addWidget(self.table)
        self.empty = QLabel("Sin perfiles. Usa + para importar o ajusta la búsqueda.")
        layout.addWidget(self.empty)
        self.pages.addWidget(profiles)
        logs = QWidget()
        layout = QVBoxLayout(logs)
        layout.addWidget(QLabel("<h3>Registro de operaciones</h3>"))
        self.log_profile = QComboBox()
        self.log_profile.addItem("Todos los perfiles", "")
        for profile in self.backend.profiles:
            self.log_profile.addItem(profile.name, profile.id)
        layout.addWidget(self.log_profile)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        copy = QPushButton("Copiar diagnóstico")
        copy.clicked.connect(self.copy_diagnostics)
        layout.addWidget(copy)
        self.pages.addWidget(logs)
        settings = QWidget()
        layout = QVBoxLayout(settings)
        layout.addWidget(QLabel("<h3>Configuración</h3>"))
        layout.addWidget(QLabel("Los perfiles y metadatos se conservan en SQLite.\n"
                                "OpenVPN 3 utiliza D-Bus; WireGuard: habilitación inicial para conectar sin contraseña administrativa.\n"
                                "Cerrar la ventana no desconecta las VPN activas."))
        self.ipv4_only = QCheckBox("Mostrar sólo IPv4 en la columna IP VPN")
        self.ipv4_only.setChecked(self.preferences.value('display/ipv4_only', False, type=bool))
        self.ipv4_only.setToolTip("Oculta IPv6 en la tabla; no cambia las direcciones ni la configuración de la VPN.")
        self.ipv4_only.toggled.connect(self.set_ipv4_only)
        layout.addWidget(self.ipv4_only)
        permissions = QPushButton("Habilitar WireGuard")
        permissions.clicked.connect(self.configure_permissions)
        layout.addWidget(permissions)
        reset = QPushButton("Actualizar estados")
        reset.clicked.connect(self.backend.observe)
        layout.addWidget(reset)
        layout.addStretch()
        self.pages.addWidget(settings)
        for page in (dashboard, profiles, logs, settings):
            page.layout().setContentsMargins(4, 0, 0, 0)
        # Los textos informativos se ajustan también en ventanas pequeñas.
        for label in self.pages.findChildren(QLabel):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
        self.backend.changed.connect(self.refresh)
        self.backend.credential.connect(self.request_credential)
        self.nav.currentRowChanged.connect(self.navigate)
        self.search.textChanged.connect(self.refresh)
        self.protocol_tabs.currentChanged.connect(self.refresh)
        self.log_profile.currentIndexChanged.connect(self.refresh)
        self.favorites.toggled.connect(self.refresh)
        self.nav.setCurrentRow(1)
        self.refresh()
        if backend is None:
            QTimer.singleShot(0, self.first_run_permissions)
            QTimer.singleShot(0, self.scan_wireguard)

    def set_ipv4_only(self, enabled):
        self.preferences.setValue('display/ipv4_only', enabled)
        self.refresh()

    def first_run_permissions(self):
        settings = QSettings('VPN Manager', 'VPN Manager')
        if not settings.value('permissions/welcome_shown', False, type=bool):
            settings.setValue('permissions/welcome_shown', True)
            self.configure_permissions()

    def configure_permissions(self):
        dialog = PermissionsDialog(self)
        dialog.exec()
        if dialog.ready:
            self.scan_wireguard()
            self.backend.observe()

    def scan_wireguard(self):
        if self.wireguard_scan is not None:
            return
        process = QProcess(self)
        self.wireguard_scan = process
        process.setProgram('/usr/bin/python3')
        process.setArguments(['-I', str(WORKER)])
        request = {'operation': 'wg-list', 'profile': {'id': str(uuid4()), 'protocol': Protocol.WIREGUARD.value}}
        process.started.connect(lambda: process.write((json.dumps(request) + '\n').encode()))
        timer = QTimer(process)
        timer.setSingleShot(True)
        timer.timeout.connect(process.kill)
        def complete(code=1, *_args):
            if self.wireguard_scan is not process:
                return
            self.wireguard_scan = None
            timer.stop()
            process.readAllStandardError()
            try:
                reply = json.loads(bytes(process.readAllStandardOutput()).decode())
                if code or reply.get('event') != 'result':
                    raise ValueError(reply.get('message', 'Habilita WireGuard para leer /etc/wireguard.'))
                self.repository.discover_wireguard(reply.get('profiles', []))
                self.reload_profiles()
                if reply.get('rejected'):
                    self.backend.logs.append(('WireGuard', f"Se omitieron {reply['rejected']} perfiles por formato o permisos no admitidos."))
            except (ValueError, OSError, TypeError, KeyError):
                self.backend.logs.append(('WireGuard', 'No se pudo leer /etc/wireguard. Comprueba la habilitación en Configuración.'))
            self.refresh()
            process.deleteLater()
        process.finished.connect(complete)
        process.errorOccurred.connect(lambda error: complete() if error == QProcess.ProcessError.FailedToStart else None)
        timer.start(30000)
        process.start()

    def navigate(self, index: int) -> None:
        self.pages.setCurrentIndex({0: 0, 1: 1, 2: 1, 3: 2, 4: 3}[index])
        self.title.setText(f"<h3>{self.nav.item(index).text()}</h3>")
        self.favorites.setVisible(index != 2)
        self.refresh()

    def refresh(self, *_args) -> None:
        sessions = self.backend.sessions
        active = sum(s.state == State.CONNECTED for s in sessions.values())
        ovpn = sum(p.protocol == Protocol.OPENVPN for p in self.backend.profiles)
        self.summary.setText(f"Perfiles: {len(sessions)}     Activas: {active}\n"
                             f"OpenVPN: {ovpn}     WireGuard: {len(sessions) - ovpn}")
        visible = [p for p in self.backend.profiles if matches(
            p, sessions[p.id], query=self.search.text(),
            protocol=self.protocol_tabs.tabData(self.protocol_tabs.currentIndex()),
            favorites_only=self.favorites.isChecked() or self.nav.currentRow() == 2)]
        self.table.setRowCount(len(visible))
        self.empty.setVisible(not visible)
        for row, profile in enumerate(visible):
            session = sessions[profile.id]
            state = session.state
            addresses = session.ip_addresses if state == State.CONNECTED and not session.simulated else ()
            if self.ipv4_only.isChecked():
                ipv4 = []
                for address in addresses:
                    try:
                        if ipaddress.ip_interface(address).version == 4:
                            ipv4.append(address)
                    except ValueError:
                        continue
                addresses = tuple(ipv4)
            for column, text in enumerate((
                ("★ " if profile.favorite else "") + profile.name,
                profile.protocol.value, profile.comment, state.value,
                ", ".join(addresses) if addresses else "—",
            )):
                item = QTableWidgetItem(text)
                if column == 3:
                    item.setToolTip(session.last_error or ("Interfaz WireGuard activa; handshake no verificado." if profile.protocol == Protocol.WIREGUARD and state == State.CONNECTED else "Estado observado en el sistema."))
                elif column in (0, 2):
                    item.setToolTip(profile.comment or "Sin comentario")
                elif column == 4:
                    item.setToolTip("\n".join(addresses) if addresses else
                                    "Sin dirección IPv4 observada." if self.ipv4_only.isChecked() and state == State.CONNECTED else
                                    "IP no disponible: sin sesión real activa o sin dirección observada.")
                self.table.setItem(row, column, item)
            job = self.backend.jobs.get(profile.id)
            stopping = bool(job and (job['operation'] == 'cancel' or job.get('cancel_requested')))
            action_text = ("Deteniendo…" if stopping else "Detener" if state == State.CONNECTING
                           else "Desconectando…" if state == State.DISCONNECTING
                           else "Desconectar" if state == State.CONNECTED
                           else "Consultar" if state == State.UNKNOWN else "Conectar")
            button = QPushButton(action_text)
            button.setToolTip(session.last_error or "Controlar la conexión con las herramientas del sistema")
            button.setEnabled(not stopping and state != State.DISCONNECTING
                              and (state == State.CONNECTING or not self.backend.active_operation(profile.id)))
            button.clicked.connect(lambda checked=False, pid=profile.id: self.toggle(pid))
            self.table.setCellWidget(row, 5, button)
            detail = QPushButton("…")
            detail.setFixedWidth(30)
            detail.setAccessibleName(f"Ver detalle de {profile.name}")
            detail.setToolTip("Ver detalle del perfil")
            detail.clicked.connect(lambda checked=False, p=profile, button=detail: self.profile_menu(p, button))
            self.table.setCellWidget(row, 6, detail)
        selected = self.log_profile.currentData()
        self.log_profile.blockSignals(True)
        self.log_profile.clear()
        self.log_profile.addItem("Todos los perfiles", "")
        for profile in self.backend.profiles:
            self.log_profile.addItem(profile.name, profile.id)
        self.log_profile.setCurrentIndex(max(0, self.log_profile.findData(selected)))
        self.log_profile.blockSignals(False)
        selected = self.log_profile.currentData()
        self.log_text.setPlainText("\n".join(
            f"[{pid}] {message}" for pid, message in self.backend.logs if not selected or pid == selected
        ) or "Sin eventos de operaciones.")

    def reload_profiles(self) -> None:
        self.backend.sync(self.repository.list())

    def add_profile(self, protocol: Protocol) -> None:
        dialog = ProfileDialog(protocol, parent=self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                profile = (dialog.imported_profile if protocol == Protocol.WIREGUARD else
                           import_profile(dialog.path.text(), protocol, dialog.name.text(),
                                          dialog.comment.toPlainText(), dialog.favorite.isChecked()))
                if profile is None:
                    return
                self.repository.add(profile)
                self.search.clear()
                self.favorites.setChecked(False)
                self.nav.setCurrentRow(1)
                for index in range(self.protocol_tabs.count()):
                    if self.protocol_tabs.tabData(index) == protocol.value:
                        self.protocol_tabs.setCurrentIndex(index)
                        break
                self.reload_profiles()
                return
            except ValueError as error:
                QMessageBox.warning(self, "No se pudo importar", str(error))
            except (OSError, sqlite3.Error):
                QMessageBox.warning(self, "No se pudo importar", "No se pudo leer el archivo o guardar la biblioteca. Revisa los permisos.")

    def profile_menu(self, profile, button) -> None:
        menu = QMenu(self)
        favorite = menu.addAction("Quitar de favoritos" if profile.favorite else "Marcar favorito")
        edit = menu.addAction("Editar nombre y comentario")
        info = menu.addAction("Ver ubicación")
        copy_system = None
        if profile.protocol == Protocol.WIREGUARD and Path(profile.config_path).parent != Path('/etc/wireguard') and not Path(profile.config_path).is_relative_to('/var/lib/vpn-manager/wireguard'):
            copy_system = menu.addAction("Copiar a /etc/wireguard")
        menu.addSeparator()
        remove = menu.addAction("Quitar del gestor")
        action = menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        try:
            if action == favorite:
                self.repository.update(replace(profile, favorite=not profile.favorite))
            elif action == edit:
                dialog = ProfileDialog(profile.protocol, profile, self)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                self.repository.update(replace(profile, name=dialog.name.text().strip(),
                                               comment=dialog.comment.toPlainText().strip(),
                                               favorite=dialog.favorite.isChecked()))
            elif copy_system is not None and action == copy_system:
                if self.backend.sessions[profile.id].state != State.DISCONNECTED or profile.id in self.backend.jobs:
                    QMessageBox.information(self, "Perfil en uso", "Desconecta el perfil antes de cambiar su ubicación operativa.")
                    return
                dialog = ProfileDialog(profile.protocol, profile, self, copy_to_system=True)
                if dialog.exec() != QDialog.DialogCode.Accepted or dialog.imported_profile is None:
                    return
                self.repository.relocate(dialog.imported_profile)
            elif action == info:
                box = QMessageBox(self)
                box.setWindowTitle("Ubicación del perfil")
                from PySide6.QtCore import Qt
                box.setTextFormat(Qt.TextFormat.PlainText)
                box.setText(profile.config_path)
                box.exec()
                return
            elif action == remove:
                if self.backend.sessions[profile.id].state != State.DISCONNECTED or profile.id in self.backend.jobs:
                    QMessageBox.information(self, "Perfil en uso", "Confirma primero que el perfil esté desconectado y sin operaciones pendientes.")
                    return
                if QMessageBox.question(self, "Quitar perfil", "¿Quitar este perfil del gestor? El archivo original se conservará.") != QMessageBox.StandardButton.Yes:
                    return
                self.repository.remove(profile.id)
                self.backend.logs = [(pid, message) for pid, message in self.backend.logs if pid != profile.id]
            else:
                return
            self.reload_profiles()
        except ValueError as error:
            QMessageBox.warning(self, "Error de biblioteca", str(error))
        except sqlite3.Error:
            QMessageBox.warning(self, "Error de biblioteca", "No se pudo guardar el cambio. Revisa los permisos y el espacio disponible.")

    def request_credential(self, profile_id: str, label: str, secret: bool) -> None:
        profile = next((p for p in self.backend.profiles if p.id == profile_id), None)
        if profile is None:
            self.backend.provide_credential(profile_id)
            return
        value, accepted = QInputDialog.getText(
            self, "Autenticación OpenVPN 3", f"{profile.name}\n{label}",
            QLineEdit.EchoMode.Password if secret else QLineEdit.EchoMode.Normal)
        self.backend.provide_credential(profile_id, value if accepted else None)

    def closeEvent(self, event) -> None:
        if self.close_to_tray and not self.quit_requested:
            self.hide()
            event.ignore()
            return
        if self.wireguard_scan is not None:
            process, self.wireguard_scan = self.wireguard_scan, None
            process.kill()
            process.waitForFinished(1000)
        if any(self.backend.active_operation(pid) for pid in self.backend.jobs):
            QMessageBox.information(self, "Operación pendiente", "Espera a que termine la operación de conexión o desconexión antes de cerrar.")
            event.ignore()
            return
        self.backend.shutdown()
        self.repository.close()
        super().closeEvent(event)

    def toggle(self, profile_id: str) -> None:
        if self.backend.sessions[profile_id].state == State.CONNECTING:
            self.backend.stop(profile_id)
            return
        if profile_id in self.backend.jobs:
            return
        profile = next(p for p in self.backend.profiles if p.id == profile_id)
        state = self.backend.sessions[profile_id].state
        if state == State.UNKNOWN:
            self.backend.start(profile, 'status')
            return
        operation = 'disconnect' if state == State.CONNECTED else 'connect'
        self.backend.start(profile, operation)

    def copy_diagnostics(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("VPN Manager — diagnóstico\n" + self.log_text.toPlainText())
        self.statusBar().showMessage("Diagnóstico copiado", 3000)
