"""虚拟机配置持久化：JSON 存储于 %LOCALAPPDATA%/winapk。"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    d = Path(base) / "winapk"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class VMProfile:
    """一台虚拟机的持久化配置。"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "新建虚拟机"
    arch: str = "x86_64"          # x86_64 | aarch64
    cpu_cores: int = 4
    ram_mb: int = 4096
    system_image: str = ""        # GSI 系统镜像（raw img / ISO）
    data_disk: str = ""           # 数据盘 qcow2 路径
    data_disk_gb: int = 16        # 新建数据盘的默认大小
    adb_host_port: int = 5555
    extra_args: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_launch(self):
        from .qemu import VMLaunchConfig

        return VMLaunchConfig(
            name=self.name, arch=self.arch, cpu_cores=self.cpu_cores,
            ram_mb=self.ram_mb, system_image=self.system_image,
            data_disk=self.data_disk, adb_host_port=self.adb_host_port,
            extra_args=self.extra_args,
        )


class ProfileStore:
    """读写虚拟机配置文件（vms.json）。"""

    def __init__(self) -> None:
        self.path = data_dir() / "vms.json"
        self.vms: list[VMProfile] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self.vms = [VMProfile(**item) for item in raw]
            except Exception:
                self.vms = []

    def save(self) -> None:
        self.path.write_text(
            json.dumps([asdict(v) for v in self.vms], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, vm: VMProfile) -> None:
        self.vms.append(vm)
        self.save()

    def update(self, vm: VMProfile) -> None:
        self.save()

    def remove(self, vm_id: str) -> None:
        self.vms = [v for v in self.vms if v.id != vm_id]
        self.save()
