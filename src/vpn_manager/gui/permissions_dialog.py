"""Habilitación explícita inicial: la contraseña sólo la gestiona el sistema."""
import json
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from vpn_manager.core.connection_manager import WORKER

INSTALLER = Path(__file__).resolve().parents[1] / 'system' / 'permissions_installer.py'


class PermissionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Habilitar WireGuard')
        self.resize(470, 280)
        self.busy = False
        self.ready = False
        self.process = None
        self.installing = False
        layout = QVBoxLayout(self)
        explanation = QLabel(
            'Autoriza una vez el control de WireGuard para tu cuenta. Después podrás '
            'importar perfiles, conectar y desconectar sin volver a introducir la contraseña administrativa.\n\n'
            'Se instalará un componente limitado de VPN Manager y una regla de permisos '
            'sólo para ese componente. Los perfiles se validan; no se permiten comandos libres ni scripts importados. '
            'Si existe el perfil AppArmor de wg-quick, se añadirá y validará el acceso limitado a las copias privadas. La GUI seguirá como usuario normal. No se iniciará ninguna VPN durante la habilitación.')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.status = QLabel('Comprobando habilitación…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        details = QLabel('Archivos: /usr/libexec/vpn-manager/ y /etc/sudoers.d/vpn-manager-<uid>. '
                         'Una actualización, revocación o cambio de cuenta puede requerir nueva autorización.')
        details.setWordWrap(True)
        layout.addWidget(details)
        buttons = QHBoxLayout()
        self.enable = QPushButton('Autorizar una vez')
        self.enable.clicked.connect(self.install)
        buttons.addWidget(self.enable)
        self.close_button = QPushButton('Ahora no')
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.expired)
        QTimer.singleShot(0, self.probe)

    def launch(self, program, arguments, request=None, installing=False):
        self.busy = True
        self.installing = installing
        self.enable.setEnabled(False)
        self.close_button.setEnabled(False)
        self.process = QProcess(self)
        self.process.setProgram(program)
        self.process.setArguments(arguments)
        if request:
            self.process.started.connect(lambda: self.process.write((json.dumps(request)+'\n').encode()))
        self.process.finished.connect(self.complete_process)
        self.process.errorOccurred.connect(self.failed_start)
        self.timeout.start(240000 if installing else 30000)
        self.process.start()

    def probe(self):
        self.launch('/usr/bin/python3', ['-I', str(WORKER)], {
            'operation': 'permissions-status',
            'profile': {'id': str(uuid4()), 'path': '', 'fingerprint': '', 'protocol': 'WireGuard'}})

    def install(self):
        self.status.setText('Autoriza en el diálogo del sistema. Esta aplicación no recibe tu contraseña.')
        self.launch('/usr/bin/pkexec', ['/usr/bin/python3', '-I', str(INSTALLER)], installing=True)

    def failed_start(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.complete_process(-1)

    def expired(self):
        if self.busy:
            if self.installing:
                # No interrumpir un commit de sudoers a mitad. El instalador tiene
                # plazos propios por validación; el usuario puede cancelar el diálogo polkit.
                self.status.setText('La autorización sigue pendiente. Puedes cancelarla en el diálogo del sistema.')
                self.timeout.start(240000)
            else:
                self.process.kill()

    def complete_process(self, code, *_args):
        if not self.busy:
            return
        self.timeout.stop()
        installing = self.installing
        try:
            reply = json.loads(bytes(self.process.readAllStandardOutput()))
        except (ValueError, UnicodeError):
            reply = {}
        self.process.readAllStandardError()
        self.process.deleteLater()
        self.busy = False
        if not isinstance(reply, dict):
            reply = {}
        if installing and code == 0 and reply.get('ok'):
            self.status.setText('Comprobando el permiso persistente para esta cuenta…')
            self.probe()
            return
        self.ready = code == 0 and bool(reply.get('ready'))
        self.enable.setEnabled(not self.ready and reply.get('can_enable', True))
        self.close_button.setEnabled(True)
        self.close_button.setText('Cerrar' if self.ready else 'Ahora no')
        self.status.setText(reply.get('message') or reply.get('error') or
                            ('WireGuard habilitado para esta cuenta.' if self.ready else
                             'No se completó la habilitación. Requiere sudo, visudo, pkexec y un agente de autenticación del escritorio.'))

    def reject(self):
        if not self.busy:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)
