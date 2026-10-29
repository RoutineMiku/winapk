"""镜像管理：创建数据盘（qcow2）、校验系统镜像。"""

from __future__ import annotations

import subprocess
from pathlib import Path


def create_data_disk(qemu_img: Path, target: Path, size_gb: int = 16) -> None:
    """用 qemu-img 创建 qcow2 数据盘。"""
    if target.exists():
        raise FileExistsError(f"数据盘已存在: {target}")
    if qemu_img is None or not Path(qemu_img).exists():
        raise RuntimeError("未找到 qemu-img，无法创建数据盘")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(qemu_img), "create", "-f", "qcow2", str(target), f"{size_gb}G"],
        check=True, capture_output=True, text=True,
    )


def validate_system_image(path: str) -> str:
    """粗校验系统镜像，返回提示信息。"""
    p = Path(path)
    if not p.exists():
        return "文件不存在"
    size_mb = p.stat().st_size / 1024 / 1024
    if p.suffix.lower() == ".iso":
        return f"ISO 安装镜像，{size_mb:.0f} MB（将从光驱引导安装）"
    if size_mb < 64:
        return f"文件过小（{size_mb:.0f} MB），可能不是有效的 GSI 镜像"
    with open(p, "rb") as f:
        magic = f.read(16)
    if magic.startswith(b"\x1f\x8b"):
        return "这是 gzip 压缩包，请先解压得到 .img 后再导入"
    if magic.startswith(b"Android"):
        return "这是 Android sparse image，请用 simg2img 转换为 raw img 后再导入"
    if magic[:2] == b"\x53\xEF" or magic[:2] not in (b"\x00\x00",):
        pass
    return f"raw 磁盘镜像，{size_mb:.0f} MB（可直接作为系统盘引导）"
