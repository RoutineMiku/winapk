"""QEMU 后端封装：定位可执行文件、检测加速器、构建启动命令行。"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# 打包/用户内置 QEMU 的目录（把 qemu-system-*.exe、qemu-img.exe 放进来即可）
BUNDLED_QEMU_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "winapk" / "qemu"

# 常见 QEMU 安装位置（Windows）
_SEARCH_DIRS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "qemu",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "qemu",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "qemu",
    BUNDLED_QEMU_DIR,
]


@dataclass
class QemuBackend:
    """描述一套可用的 QEMU 可执行文件集合。"""

    root: Path | None = None
    system_x86_64: Path | None = None
    system_aarch64: Path | None = None
    qemu_img: Path | None = None
    accelerators: list[str] = field(default_factory=list)
    edk2_aarch64: Path | None = None

    @property
    def available(self) -> bool:
        return self.system_x86_64 is not None or self.system_aarch64 is not None

    def system_binary(self, arch: str) -> Path | None:
        return self.system_x86_64 if arch == "x86_64" else self.system_aarch64


def _find_binary(name: str, root: Path | None) -> Path | None:
    # 1) 指定的安装根目录
    if root is not None:
        p = root / name
        if p.exists():
            return p
        p_exe = root / (name + ".exe")
        if p_exe.exists():
            return p_exe
    # 2) PATH
    found = shutil.which(name)
    if found:
        return Path(found)
    # 3) 常见安装目录
    for d in _SEARCH_DIRS:
        p = d / (name + ".exe")
        if p.exists():
            return p
    return None


def detect_backend(root: Path | None = None) -> QemuBackend:
    """探测本机 QEMU 环境，包括可用的加速器与 ARM64 UEFI 固件。"""
    backend = QemuBackend(root=root)
    backend.system_x86_64 = _find_binary("qemu-system-x86_64", root)
    backend.system_aarch64 = _find_binary("qemu-system-aarch64", root)
    backend.qemu_img = _find_binary("qemu-img", root)

    probe = backend.system_x86_64 or backend.system_aarch64
    if probe is not None:
        try:
            out = subprocess.run(
                [str(probe), "-accel", "help"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            backend.accelerators = [
                ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("Accelerators")
            ]
        except Exception:
            backend.accelerators = ["tcg"]

    # ARM64 UEFI 固件（qemu 官方 Windows 构建自带）
    if backend.root is not None:
        candidates = [
            backend.root / "share" / "edk2-aarch64" / "QEMU_EFI.fd",
            backend.root / "edk2-aarch64" / "QEMU_EFI.fd",
        ]
        for c in candidates:
            if c.exists():
                backend.edk2_aarch64 = c
                break
    return backend


@dataclass
class VMLaunchConfig:
    """一次 VM 启动的全部参数。"""

    name: str
    arch: str  # x86_64 | aarch64
    cpu_cores: int = 4
    ram_mb: int = 4096
    system_image: str = ""   # GSI / ISO / raw 系统盘镜像路径
    data_disk: str = ""      # qcow2 数据盘路径
    adb_host_port: int = 5555
    extra_args: list[str] = field(default_factory=list)


def build_command(backend: QemuBackend, cfg: VMLaunchConfig, qmp_port: int = 0) -> list[str]:
    """构建完整的 QEMU 启动命令行（不执行）。"""
    binary = backend.system_binary(cfg.arch)
    if binary is None:
        raise RuntimeError(f"未找到 qemu-system-{cfg.arch}，请先安装 QEMU 或在设置中指定路径")

    # 加速器优先级：WHPX > TCG。WHPX 需要在"启用或关闭 Windows 功能"中
    # 勾选"虚拟机平台 / Windows 虚拟机监控程序平台"。
    if "whpx" in backend.accelerators:
        accel_args = ["-machine", "q35,accel=whpx:tcg" if cfg.arch == "x86_64" else "virt,accel=whpx:tcg", "-cpu", "max"]
    else:
        accel_args = (
            ["-machine", "q35,accel=tcg", "-cpu", "max"]
            if cfg.arch == "x86_64"
            else ["-machine", "virt,accel=tcg", "-cpu", "cortex-a76"]
        )

    cmd = [str(binary)]
    cmd += accel_args
    cmd += ["-smp", str(cfg.cpu_cores), "-m", str(cfg.ram_mb)]

    # ARM64 需要外部 UEFI 固件
    if cfg.arch == "aarch64" and backend.edk2_aarch64 is not None:
        cmd += ["-bios", str(backend.edk2_aarch64)]

    # 系统镜像（GSI raw img / ISO）
    if cfg.system_image:
        img = cfg.system_image
        if img.lower().endswith(".iso"):
            cmd += ["-cdrom", img, "-boot", "d"]
        else:
            cmd += ["-drive", f"file={img},format=raw,if=virtio,index=1,readonly=on"]

    # 数据盘（qcow2）
    if cfg.data_disk:
        cmd += ["-drive", f"file={cfg.data_disk},format=qcow2,if=virtio,index=0"]

    # 网络：用户态网络 + ADB 端口转发（转发到客户机 5555）
    fwd = f",hostfwd=tcp::{cfg.adb_host_port}-:5555" if cfg.adb_host_port else ""
    cmd += ["-netdev", f"user,id=n0{fwd}", "-device", "virtio-net-pci,netdev=n0"]

    # 显卡：x86_64 用 std（兼容性最好），arm64 用 virtio-gpu
    cmd += ["-device", "virtio-gpu-pci" if cfg.arch == "aarch64" else "VGA"]

    # 音频
    cmd += ["-audiodev", "wasapi,id=snd0", "-device", "intel-hda", "-device", "hda-duplex"]

    # QMP 控制通道（用于优雅关机）
    if qmp_port:
        cmd += ["-qmp", f"tcp:127.0.0.1:{qmp_port},server,nowait"]

    cmd += ["-display", "sdl"]
    cmd += cfg.extra_args
    return cmd
