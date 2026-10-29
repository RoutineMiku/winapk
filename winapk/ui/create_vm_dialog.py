"""新建虚拟机对话框。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
)

from ..core.images import validate_system_image
from ..core.qemu import QemuBackend


class CreateVMDialog(QDialog):
    def __init__(self, backend: QemuBackend, parent=None) -> None:
        super().__init__(parent)
        self.backend = backend
        self.setWindowTitle("新建虚拟机")
        self.setMinimumWidth(520)
        self._build_form()

    def _build_form(self) -> None:
        form = QFormLayout(self)

        self.ed_name = QLineEdit("我的安卓虚拟机")
        form.addRow("名称", self.ed_name)

        self.cb_arch = QComboBox()
        archs = []
        if self.backend.system_x86_64:
            archs.append(("x86_64（推荐，支持硬件加速）", "x86_64"))
        if self.backend.system_aarch64:
            archs.append(("aarch64 / ARM64（运行 ARM64 GSI，速度较慢）", "aarch64"))
        if not archs:
            archs.append(("x86_64（未检测到 QEMU）", "x86_64"))
        for label, data in archs:
            self.cb_arch.addItem(label, data)
        form.addRow("架构", self.cb_arch)

        self.sp_cpu = QSpinBox(); self.sp_cpu.setRange(1, 32); self.sp_cpu.setValue(4)
        form.addRow("CPU 核心数", self.sp_cpu)

        self.sp_ram = QSpinBox(); self.sp_ram.setRange(512, 65536); self.sp_ram.setSingleStep(512); self.sp_ram.setValue(4096)
        form.addRow("内存 (MB)", self.sp_ram)

        img_row = QHBoxLayout()
        self.ed_image = QLineEdit()
        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self._browse_image)
        img_row.addWidget(self.ed_image, 1)
        img_row.addWidget(btn_browse)
        form.addRow("GSI 系统镜像 (img/iso)", img_row)

        self.lb_image_info = QLabel("")
        self.lb_image_info.setStyleSheet("color: gray;")
        form.addRow("", self.lb_image_info)
        self.ed_image.textChanged.connect(self._update_image_info)

        self.sp_disk = QSpinBox(); self.sp_disk.setRange(2, 512); self.sp_disk.setValue(16)
        self.sp_disk.setSuffix(" GB")
        form.addRow("数据盘大小", self.sp_disk)

        self.ck_disk = QCheckBox("创建数据盘（qcow2）")
        self.ck_disk.setChecked(True)
        form.addRow("", self.ck_disk)

        self.sp_adb = QSpinBox(); self.sp_adb.setRange(1024, 65535); self.sp_adb.setValue(5555)
        form.addRow("ADB 宿主端口", self.sp_adb)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 GSI 系统镜像", "",
            "安卓镜像 (*.img *.iso);;所有文件 (*)",
        )
        if path:
            self.ed_image.setText(path)

    def _update_image_info(self) -> None:
        text = self.ed_image.text().strip()
        self.lb_image_info.setText(validate_system_image(text) if text else "")

    def _accept(self) -> None:
        if not self.ed_name.text().strip():
            self.ed_name.setFocus()
            return
        self.accept()

    def result_config(self) -> dict:
        return {
            "name": self.ed_name.text().strip(),
            "arch": self.cb_arch.currentData(),
            "cpu_cores": self.sp_cpu.value(),
            "ram_mb": self.sp_ram.value(),
            "system_image": self.ed_image.text().strip(),
            "data_disk_gb": self.sp_disk.value(),
            "create_data_disk": self.ck_disk.isChecked(),
            "adb_host_port": self.sp_adb.value(),
        }
