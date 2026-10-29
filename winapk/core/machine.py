"""VM 进程管理：基于 QProcess 启动/停止 QEMU，转发日志。"""

from __future__ import annotations

import socket
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


class VMRuntime(QObject):
    """一个正在运行的 QEMU 实例。"""

    log_line = Signal(str)
    state_changed = Signal(str)  # running / stopped / error

    def __init__(self, vm_id: str, name: str, parent=None) -> None:
        super().__init__(parent)
        self.vm_id = vm_id
        self.name = name
        self.qmp_port = self._pick_port()
        self.process: QProcess | None = None

    @staticmethod
    def _pick_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def start(self, cmd: list[str], cwd: str | None = None) -> None:
        if self.running:
            raise RuntimeError("虚拟机已在运行")
        self.process = QProcess(self)
        self.process.setProgram(cmd[0])
        self.process.setArguments(cmd[1:])
        if cwd:
            self.process.setWorkingDirectory(cwd)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._drain)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        self.log_line.emit(f"[winapk] 启动: {Path(cmd[0]).name} ...")
        self.process.start()
        self.state_changed.emit("running")

    def _drain(self) -> None:
        if self.process is None:
            return
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        for line in text.splitlines():
            if line.strip():
                self.log_line.emit(line)

    def _on_finished(self, code: int, _status) -> None:
        self.log_line.emit(f"[winapk] 虚拟机已退出（exit code {code}）")
        self.state_changed.emit("stopped")

    def _on_error(self, err) -> None:
        if not self.running:
            self.log_line.emit(f"[winapk] 启动失败: {err}")
            self.state_changed.emit("error")

    def shutdown(self) -> None:
        """先尝试 QMP 优雅关机，超时则强制结束进程。"""
        if not self.running:
            return
        try:
            with socket.create_connection(("127.0.0.1", self.qmp_port), timeout=2) as s:
                f = s.makefile("rw", encoding="utf-8", newline="\n")
                f.readline()  # greeting
                f.write('{"execute":"qmp_capabilities"}\n'); f.flush()
                f.readline()
                f.write('{"execute":"system_powerdown"}\n'); f.flush()
                f.readline()
        except Exception:
            pass
        if not self.process.waitForFinished(5000):
            self.process.kill()


class RuntimeManager(QObject):
    """管理所有 VMRuntime，键为 vm_id。"""

    log_line = Signal(str, str)        # vm_id, line
    state_changed = Signal(str, str)   # vm_id, state

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.runtimes: dict[str, VMRuntime] = {}

    def runtime(self, vm_id: str) -> VMRuntime:
        if vm_id not in self.runtimes:
            raise KeyError(vm_id)
        return self.runtimes[vm_id]

    def is_running(self, vm_id: str) -> bool:
        rt = self.runtimes.get(vm_id)
        return rt is not None and rt.running

    def start(self, vm_id: str, vm_name: str, cmd: list[str]) -> None:
        if self.is_running(vm_id):
            raise RuntimeError("虚拟机已在运行")
        rt = VMRuntime(vm_id, vm_name, self)
        rt.qmp_port = rt.qmp_port
        rt.log_line.connect(lambda line, vid=vm_id: self.log_line.emit(vid, line))
        rt.state_changed.connect(lambda st, vid=vm_id: self.state_changed.emit(vid, st))
        self.runtimes[vm_id] = rt
        rt.start(cmd)

    def stop(self, vm_id: str) -> None:
        self.runtime(vm_id).shutdown()

    def stop_all(self) -> None:
        for rt in list(self.runtimes.values()):
            rt.shutdown()
