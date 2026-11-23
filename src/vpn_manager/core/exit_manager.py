"""Salida comprobada: observar, confirmar, desconectar y volver a observar."""
import time
from PySide6.QtCore import QObject, QTimer, Signal
from .models import State


class ExitManager(QObject):
    finished = Signal(bool, str)

    def __init__(self, backend, confirm, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.confirm = confirm
        self.running = False
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.advance)

    def start(self):
        if self.running:
            return
        self.running = True
        self.consented = False
        self.poll_active = self.backend.poll.isActive()
        self.backend.poll.stop()
        self.backend.pending.clear()
        self.deadline = time.monotonic() + 300
        self.phase = 'settle'
        self.current = None
        self.queue = []
        if any(s.state in (State.CONNECTED, State.CONNECTING, State.DISCONNECTING) for s in self.backend.sessions.values()) or any(self.backend.active_operation(pid) for pid in self.backend.jobs):
            if not self.confirm():
                self.finish(False)
                return
            self.consented = True
        self.timer.start()
        self.advance()

    def finish(self, success, message=''):
        self.timer.stop()
        self.running = False
        if not success and self.poll_active:
            self.backend.poll.start()
        self.finished.emit(success, message)

    def scan(self, final=False):
        self.phase = 'verify' if final else 'check'
        self.queue = list(self.backend.profiles)
        self.snapshot = {p.id for p in self.queue}
        self.current = None

    def advance(self):
        if not self.running:
            return
        if time.monotonic() >= self.deadline:
            self.finish(False, 'No se confirmó la desconexión a tiempo. El programa seguirá abierto; revisa los Logs.')
            return
        if self.phase == 'settle':
            for pid, job in tuple(self.backend.jobs.items()):
                if self.consented and job['operation'] == 'connect':
                    self.backend.stop(pid)
            if self.backend.jobs:
                return
            self.scan()
        if {p.id for p in self.backend.profiles} != self.snapshot:
            self.finish(False, 'La lista de perfiles cambió durante la comprobación. Vuelve a intentar salir.')
            return
        if self.current is not None:
            if self.current in self.backend.jobs:
                return
            state = self.backend.sessions[self.current].state
            if state not in (State.CONNECTED, State.DISCONNECTED) or (self.phase == 'disconnect' and state != State.DISCONNECTED):
                self.finish(False, 'No se pudo confirmar el estado o desconectar una VPN. El programa seguirá abierto; revisa los Logs.')
                return
            self.current = None
        if self.queue:
            profile = self.queue.pop(0)
            self.current = profile.id
            self.backend.start(profile, 'disconnect' if self.phase == 'disconnect' else 'status')
            return
        active = [p for p in self.backend.profiles if self.backend.sessions[p.id].state != State.DISCONNECTED]
        if self.phase == 'verify':
            if active or self.backend.jobs:
                self.finish(False, 'Todavía hay una VPN activa o una operación pendiente. El programa seguirá abierto.')
            else:
                self.finish(True)
        elif self.phase == 'disconnect':
            self.scan(final=True)
        elif not active:
            self.finish(True)
        else:
            if not self.consented:
                if not self.confirm():
                    self.finish(False)
                    return
                self.consented = True
            self.phase = 'disconnect'
            self.queue = active
