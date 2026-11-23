"""Coordinación Qt asíncrona con un proceso aislado por operación/perfil."""
from dataclasses import replace
import json
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from .models import Profile, Session, State

WORKER = Path(__file__).resolve().parents[1] / 'system' / 'worker.py'


class ConnectionManager(QObject):
    changed = Signal()
    credential = Signal(str, str, bool)

    def __init__(self, profiles: tuple[Profile, ...], parent=None, *, auto_poll=True, worker_path=WORKER):
        super().__init__(parent)
        self.worker_path = Path(worker_path)
        self.profiles = profiles
        self.sessions = {p.id: Session(p.id, State.UNKNOWN, simulated=False) for p in profiles}
        self.logs: list[tuple[str, str]] = []
        self.jobs: dict[str, dict] = {}
        self.pending = []
        self.closing = False
        self.poll = QTimer(self)
        self.poll.setInterval(5000)
        self.poll.timeout.connect(self.observe)
        if auto_poll:
            self.poll.start()
            QTimer.singleShot(0, self.observe)

    def sync(self, profiles):
        self.profiles = profiles
        self.sessions = {p.id: self.sessions.get(p.id, Session(p.id, State.UNKNOWN, simulated=False)) for p in profiles}
        self.changed.emit()
        if self.poll.isActive():
            self.observe()

    def observe(self):
        if self.closing or self.pending:
            return
        self.pending = [p for p in self.profiles if p.id not in self.jobs]
        self.drain_observations()

    def drain_observations(self):
        current_ids = {p.id for p in self.profiles}
        while self.pending and len(self.jobs) < 4 and not self.closing:
            profile = self.pending.pop(0)
            if profile.id in current_ids and profile.id not in self.jobs:
                self.start(profile, 'status')

    def active_operation(self, profile_id):
        job = self.jobs.get(profile_id)
        return bool(job and job['operation'] != 'status')

    def start(self, profile: Profile, operation: str):
        if profile.id in self.jobs:
            return
        process = QProcess(self)
        timeout = QTimer(self)
        timeout.setSingleShot(True)
        job = {'process': process, 'timeout': timeout, 'buffer': b'', 'operation': operation,
               'received': False, 'failed': False, 'profile': profile, 'cancel_requested': False}
        self.jobs[profile.id] = job
        process.setProgram('/usr/bin/python3')
        process.setArguments(['-I', str(self.worker_path)])
        def send_request():
            process.write((json.dumps({
                'operation': operation, 'profile': {'id': profile.id, 'protocol': profile.protocol.value,
                    'path': profile.config_path, 'fingerprint': profile.fingerprint},
            }) + '\n').encode())
            if job['cancel_requested']:
                process.write(b'{"cancel":true}\n')
        process.started.connect(send_request)
        process.readyReadStandardOutput.connect(lambda: self.read(profile.id))
        # Descartar stderr: mensajes de librerías externas podrían contener secretos.
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(lambda code, status: self.finished(profile.id, code))
        process.errorOccurred.connect(lambda error: self.process_error(profile.id, error))
        timeout.timeout.connect(lambda: self.expired(profile.id))
        if operation != 'status':
            state = State.CONNECTING if operation == 'connect' else State.DISCONNECTING
            self.sessions[profile.id] = replace(self.sessions[profile.id], state=state, ip_addresses=())
            self.record(profile.id, state.value)
            self.changed.emit()
        timeout.start(30000 if operation == 'status' else 240000)
        process.start()

    def record(self, profile_id, message):
        if not self.logs or self.logs[-1] != (profile_id, message):
            self.logs.append((profile_id, message))
            self.logs = self.logs[-1000:]

    def read(self, profile_id):
        job = self.jobs.get(profile_id)
        if not job:
            return
        job['buffer'] += bytes(job['process'].readAllStandardOutput())
        if len(job['buffer']) > 1024 * 1024:
            self.fail(profile_id, 'Respuesta del backend demasiado grande.')
            job['process'].kill()
            return
        while b'\n' in job['buffer']:
            line, job['buffer'] = job['buffer'].split(b'\n', 1)
            try:
                event = json.loads(line)
                if event['event'] == 'credential':
                    if job['cancel_requested']:
                        self.provide_credential(profile_id)
                    else:
                        self.credential.emit(profile_id, event['label'], bool(event['secret']))
                elif event['event'] == 'result':
                    state = State(event['state'])
                    previous = self.sessions[profile_id]
                    if job['cancel_requested']:
                        job['received'] = True
                        continue  # Una conexión tardía nunca revierte Deteniendo.
                    self.sessions[profile_id] = replace(previous, state=state, simulated=False,
                        ip_addresses=tuple(event.get('ip_addresses', ())) if state == State.CONNECTED else (),
                        interface=event.get('interface', ''), last_error=event.get('error', ''))
                    job['received'] = True
                    if previous.state != state:
                        self.record(profile_id, state.value)
                    if event.get('error'):
                        self.record(profile_id, event['error'])
                    self.changed.emit()
                elif event['event'] == 'error':
                    self.fail(profile_id, event['message'])
                else:
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                self.fail(profile_id, 'Respuesta de backend no reconocida.')

    def stop(self, profile_id):
        job = self.jobs.get(profile_id)
        if job and job['operation'] == 'connect' and not job['cancel_requested']:
            job['cancel_requested'] = True
            self.sessions[profile_id] = replace(self.sessions[profile_id], state=State.DISCONNECTING, ip_addresses=())
            self.record(profile_id, 'Cancelación solicitada; comprobando desconexión.')
            if job['process'].state() == QProcess.ProcessState.Running:
                job['process'].write(b'{"cancel":true}\n')
            self.changed.emit()
        elif job is None:
            profile = next(p for p in self.profiles if p.id == profile_id)
            self.start(profile, 'cancel')

    def provide_credential(self, profile_id, value=None):
        job = self.jobs.get(profile_id)
        if job:
            payload = {'cancel': True} if value is None else {'value': value}
            job['process'].write((json.dumps(payload) + '\n').encode())

    def fail(self, profile_id, message):
        job = self.jobs.get(profile_id)
        if not job or job['failed']:
            return
        job['failed'] = True
        if job['cancel_requested']:
            self.record(profile_id, message)
            return  # La cancelación posterior comprobará el estado resultante.
        state = State.UNKNOWN if job['operation'] == 'status' else State.ERROR
        self.sessions[profile_id] = replace(self.sessions[profile_id], state=state, ip_addresses=(), last_error=message)
        self.record(profile_id, message)
        self.changed.emit()

    def expired(self, profile_id):
        job = self.jobs.get(profile_id)
        if job:
            self.fail(profile_id, 'Tiempo de espera agotado; actualiza el estado antes de reintentar.')
            job['process'].kill()

    def process_error(self, profile_id, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.fail(profile_id, 'No se pudo iniciar el trabajador con Python del sistema.')
            self.finished(profile_id, -1)

    def finished(self, profile_id, code):
        if profile_id not in self.jobs:
            return
        self.read(profile_id)
        job = self.jobs[profile_id]
        if not job['cancel_requested'] and (code != 0 or not job['received']):
            self.fail(profile_id, 'El trabajador terminó sin confirmar el resultado; actualiza el estado.')
        self.jobs.pop(profile_id)
        job['timeout'].stop()
        job['timeout'].deleteLater()
        job['process'].deleteLater()
        if job['cancel_requested'] and not self.closing:
            self.start(job['profile'], 'cancel')
        self.drain_observations()
        self.changed.emit()

    def shutdown(self):
        self.closing = True
        self.pending.clear()
        self.poll.stop()
        for job in tuple(self.jobs.values()):
            job['timeout'].stop()
            job['process'].kill()
            job['process'].waitForFinished(1000)
