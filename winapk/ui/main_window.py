"""主窗口：虚拟机列表 + 详情 + 日志面板。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import __app_name__, __version__
from ..core.images import create_data_disk, validate_system_image
from ..core.machine import RuntimeManager
from ..core.qemu import QemuBackend, build_command, detect_backend
from ..core.store import ProfileStore, VMProfile, data_dir
from .create_vm_dialog import CreateVMDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} - 安卓 GSI 虚拟机管理器 v{__version__}")
        self.resize(980, 640)

        self.store = ProfileStore()
        self.backend: QemuBackend = detect_backend()
        self.runtimes = RuntimeManager(self)
        self.runtimes.log_line.connect(self._on_runtime_log)
        self.runtimes.state_changed.connect(self._on_runtime_state)

        self._build_ui()
        self._refresh_vm_list()
        self._refresh_backend_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QHBoxLayout(central)

        # 左侧：虚拟机列表 + 操作按钮
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("我的虚拟机"))
        self.vm_list = QListWidget()
        self.vm_list.currentRowChanged.connect(self._on_select_vm)
        lv.addWidget(self.vm_list, 1)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("新建")
        self.btn_start = QPushButton("启动")
        self.btn_stop = QPushButton("关机")
        self.btn_delete = QPushButton("删除")
        for b in (self.btn_new, self.btn_start, self.btn_stop, self.btn_delete):
            btn_row.addWidget(b)
        lv.addLayout(btn_row)
        self.btn_new.clicked.connect(self._on_create_vm)
        self.btn_start.clicked.connect(self._on_start_vm)
        self.btn_stop.clicked.connect(self._on_stop_vm)
        self.btn_delete.clicked.connect(self._on_delete_vm)

        # 右侧：详情 + 日志
        right_split = QSplitter(Qt.Vertical)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setPlaceholderText("虚拟机运行日志将显示在这里…")
        right_split.addWidget(self.detail)
        right_split.addWidget(self.log_view)
        right_split.setSizes([280, 320])

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right_split)
        split.setSizes([280, 700])
        root.addWidget(split)
        self.setCentralWidget(central)

        self._selected: str | None = None

    def _refresh_backend_status(self) -> None:
        be = self.backend
        if be.available:
            acc = "、".join(be.accelerators) or "tcg"
            hint = "WHPX 硬件加速已启用 ✓" if "whpx" in acc else "未检测到 WHPX，将以 TCG 软件模拟运行（较慢）。可在\"启用或关闭 Windows 功能\"中开启\"虚拟机平台\"获得硬件加速。"
            self.statusBar().showMessage(
                f"QEMU 后端: {be.root or 'PATH'} | 加速器: {acc} | {hint}", 0
            )
        else:
            self.statusBar().showMessage(
                "未检测到 QEMU！请安装 QEMU（https://qemu.weilnetz.de/w64/）后重启本程序，"
                "或将 QEMU 安装目录下的 qemu-system-x86_64.exe 等文件放入 "
                f"{data_dir() / 'qemu'}",
                0,
            )

    # ------------------------------------------------------------- 列表逻辑
    def _refresh_vm_list(self) -> None:
        self.vm_list.clear()
        for vm in self.store.vms:
            running = self.runtimes.is_running(vm.id)
            item = QListWidgetItem(f"{'🟢 ' if running else '⚪ '}{vm.name}（{vm.arch}）")
            item.setData(Qt.UserRole, vm.id)
            self.vm_list.addItem(item)

    def _current_vm(self) -> VMProfile | None:
        row = self.vm_list.currentRow()
        if row < 0:
            return None
        vm_id = self.vm_list.item(row).data(Qt.UserRole)
        for vm in self.store.vms:
            if vm.id == vm_id:
                return vm
        return None

    def _on_select_vm(self, _row: int) -> None:
        vm = self._current_vm()
        self._selected = vm.id if vm else None
        if vm is None:
            self.detail.clear()
            return
        running = self.runtimes.is_running(vm.id)
        self.detail.setHtml(
            f"<h2>{vm.name}</h2>"
            f"<table cellpadding='4'>"
            f"<tr><td><b>架构</b></td><td>{vm.arch}</td></tr>"
            f"<tr><td><b>CPU / 内存</b></td><td>{vm.cpu_cores} 核 / {vm.ram_mb} MB</td></tr>"
            f"<tr><td><b>系统镜像</b></td><td>{vm.system_image or '（未导入）'}</td></tr>"
            f"<tr><td><b>数据盘</b></td><td>{vm.data_disk or '（未创建）'}</td></tr>"
            f"<tr><td><b>ADB 端口</b></td><td>127.0.0.1:{vm.adb_host_port} → 客户机 5555</td></tr>"
            f"<tr><td><b>状态</b></td><td>{'🟢 运行中' if running else '⚪ 已停止'}</td></tr>"
            f"</table>"
            f"<p>提示：启动后可用 <code>adb connect 127.0.0.1:{vm.adb_host_port}</code> 连接此虚拟机。</p>"
        )

    # ------------------------------------------------------------- 动作
    def _on_create_vm(self) -> None:
        dlg = CreateVMDialog(self.backend, self)
        if dlg.exec() != QDialog.Accepted:
            return
        cfg = dlg.result_config()
        vm = VMProfile(
            name=cfg["name"], arch=cfg["arch"], cpu_cores=cfg["cpu_cores"],
            ram_mb=cfg["ram_mb"], system_image=cfg["system_image"],
            adb_host_port=cfg["adb_host_port"],
        )
        # 创建数据盘
        if cfg["create_data_disk"]:
            disk = data_dir() / "disks" / f"{vm.id}_data.qcow2"
            try:
                create_data_disk(self.backend.qemu_img, disk, cfg["data_disk_gb"])
                vm.data_disk = str(disk)
            except Exception as e:
                QMessageBox.warning(self, "数据盘创建失败", str(e))
        self.store.add(vm)
        self._refresh_vm_list()
        self.vm_list.setCurrentRow(len(self.store.vms) - 1)

    def _on_start_vm(self) -> None:
        vm = self._current_vm()
        if vm is None:
            QMessageBox.information(self, "提示", "请先选择或新建一台虚拟机")
            return
        if self.runtimes.is_running(vm.id):
            return
        if not self.backend.available:
            QMessageBox.critical(
                self, "缺少 QEMU",
                "未检测到 QEMU。请安装后重启 WinApk：\nhttps://qemu.weilnetz.de/w64/\n\n"
                f"也可以把 QEMU 文件放入: {data_dir() / 'qemu'}",
            )
            return
        if not vm.system_image:
            QMessageBox.warning(self, "缺少系统镜像", "这台虚拟机还没有导入 GSI 系统镜像，请编辑或新建虚拟机时选择镜像文件。")
            return
        try:
            # 为本次启动分配 QMP 端口
            from ..core.machine import VMRuntime
            qmp_port = VMRuntime._pick_port()
            cmd = build_command(self.backend, vm.to_launch(), qmp_port=qmp_port)
            self.runtimes.start(vm.id, vm.name, cmd)
            self._refresh_vm_list()
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))

    def _on_stop_vm(self) -> None:
        vm = self._current_vm()
        if vm and self.runtimes.is_running(vm.id):
            self.runtimes.stop(vm.id)

    def _on_delete_vm(self) -> None:
        vm = self._current_vm()
        if vm is None:
            return
        if self.runtimes.is_running(vm.id):
            QMessageBox.warning(self, "无法删除", "请先关闭正在运行的虚拟机。")
            return
        if QMessageBox.question(self, "删除虚拟机", f"确定删除「{vm.name}」吗？（数据盘文件不会被删除）") != QMessageBox.Yes:
            return
        self.store.remove(vm.id)
        self._refresh_vm_list()
        self.detail.clear()

    # ------------------------------------------------------------- 日志/状态
    def _on_runtime_log(self, vm_id: str, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_runtime_state(self, vm_id: str, state: str) -> None:
        self._refresh_vm_list()
        if self._selected == vm_id:
            self._on_select_vm(self.vm_list.currentRow())

    def closeEvent(self, event) -> None:  # noqa: N802
        self.runtimes.stop_all()
        super().closeEvent(event)
