"""Instancia única por usuario y bandeja del escritorio, sin operaciones VPN."""
import fcntl
import os
from pathlib import Path
import socket
import stat
import tempfile
import time
from PySide6.QtCore import QObject, QSocketNotifier, QStandardPaths, Signal, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, parent=None, *, directory=None):
        super().__init__(parent)
        runtime = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
        self.directory = Path(directory) if directory else Path(runtime or tempfile.gettempdir()) / f'vpn-manager-{os.getuid()}'
        self.directory.mkdir(mode=0o700, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise OSError('El directorio de la instancia no tiene permisos privados.')
        self.path = self.directory/'gui.sock'
        self.lock = None
        self.server = None
        self.notifier = None

    def acquire(self):
        descriptor = os.open(self.directory/'gui.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise OSError('Archivo de bloqueo inválido.')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return False
        self.lock = descriptor
        try:
            self.path.unlink(missing_ok=True)  # Sólo quien posee el bloqueo retira sockets obsoletos.
            self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server.bind(str(self.path))
            self.path.chmod(0o600)
            self.server.listen(8)
            self.server.setblocking(False)
            self.notifier = QSocketNotifier(self.server.fileno(), QSocketNotifier.Type.Read, self)
            self.notifier.activated.connect(self.receive)
        except Exception:
            self.close()
            raise
        return True

    def activate_existing(self):
        # El primer proceso puede tener el bloqueo y estar creando el socket todavía.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(0.2)
                    client.connect(str(self.path))
                return True
            except OSError:
                time.sleep(0.05)
        return False

    def receive(self, *_args):
        if self.server is None:
            return
        # No leer datos del cliente: la única operación admitida es mostrar la ventana.
        for _ in range(8):
            try:
                client, _ = self.server.accept()
            except BlockingIOError:
                break
            client.close()
            self.activated.emit()

    def close(self):
        if self.notifier is not None:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.server is not None:
            self.server.close()
            self.server = None
        if self.lock is not None:
            self.path.unlink(missing_ok=True)
            os.close(self.lock)
            self.lock = None
        # No borrar gui.lock: otra instancia podría estar bloqueando el mismo inode.


def application_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor('#247cba'))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor('white'))
    font = painter.font(); font.setPixelSize(24); font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'VPN')
    painter.end()
    return QIcon.fromTheme('network-vpn', QIcon(pixmap))


class DesktopIntegration(QObject):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        from vpn_manager.core.exit_manager import ExitManager
        self.exit_manager = ExitManager(window.backend, self.confirm_exit, self)
        self.exit_manager.finished.connect(self.finish_exit)
        icon = application_icon()
        QApplication.instance().setWindowIcon(icon)
        window.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.menu = QMenu(window)
        self.menu.addAction('Mostrar VPN Manager', self.show_window)
        self.menu.addSeparator()
        self.exit_action = self.menu.addAction('Salir', self.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip('VPN Manager')
        self.tray.activated.connect(self.activate)
        available = QSystemTrayIcon.isSystemTrayAvailable()
        window.close_to_tray = available
        if available:
            QApplication.instance().setQuitOnLastWindowClosed(False)
            self.tray.show()
        else:
            window.statusBar().showMessage('El escritorio no ofrece bandeja del sistema; cerrar la ventana saldrá de la aplicación.')

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        dialog = QApplication.activeModalWidget()
        if dialog is not None:
            dialog.raise_()
            dialog.activateWindow()

    def activate(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if QApplication.activeModalWidget() is not None:
                self.show_window()
            elif self.window.isVisible() and not self.window.isMinimized():
                self.window.hide()
            else:
                self.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def confirm_exit(self):
        return QMessageBox.question(
            self.window, 'Salir de VPN Manager',
            'Hay conexiones VPN activas o en proceso. Para salir deben desconectarse.\n\n'
            '¿Quieres cerrar las conexiones y salir?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def quit(self):
        if self.exit_manager.running:
            return
        dialog = QApplication.activeModalWidget()
        if dialog is not None:
            self.show_window()
            return
        self.previous_enabled = self.window.isEnabled()
        self.window.setEnabled(False)
        self.exit_action.setEnabled(False)
        self.window.statusBar().showMessage('Comprobando conexiones antes de salir…')
        self.exit_manager.start()

    def finish_exit(self, success, message):
        self.window.setEnabled(self.previous_enabled)
        self.exit_action.setEnabled(True)
        self.window.statusBar().clearMessage()
        if not success:
            if message:
                QMessageBox.warning(self.window, 'No se pudo salir', message)
            return
        self.window.quit_requested = True
        if self.window.close():
            self.tray.hide()
            QApplication.instance().quit()
        else:
            self.window.quit_requested = False
