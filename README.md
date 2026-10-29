# WinApk — Windows 原生安卓 GSI 虚拟机管理器

把"在安卓上运行 GSI 虚拟机"的体验带到 Windows 桌面：导入 GSI/ISO 镜像，一键启动一台完整的安卓虚拟机。

## 功能

- 📱 虚拟机管理：新建 / 启动 / 关机（QMP 优雅关机）/ 删除
- 🖼️ 镜像导入：支持 raw `.img` GSI 与 `.iso` 安装镜像，自动识别 sparse/gzip 并提示转换
- 💾 数据盘：基于 `qemu-img` 自动创建 qcow2 数据盘
- ⚡ 硬件加速：优先使用 WHPX（Windows Hypervisor Platform），未开启时回退 TCG
- 🌐 网络：用户态网络 + ADB 端口转发（`adb connect 127.0.0.1:5555`）
- 🖥️ 两种架构：x86_64（推荐，快）与 aarch64（跑 ARM64 GSI，TCG 模拟较慢）

## 快速开始

1. **安装 QEMU**（一次性依赖）：
   下载 <https://qemu.weilnetz.de/w64/> 安装包安装；
   或把 QEMU 安装目录中的 `qemu-system-x86_64.exe`、`qemu-img.exe` 等复制到
   `%LOCALAPPDATA%\winapk\qemu\`。
2. **获取 GSI 镜像**：
   - x86_64：从 Android-x86 / Bliss OS 下载 x86_64 ISO，或使用 AOSP 发布的 `x86_64` GSI
   - ARM64 GSI：AOSP/phhusson GSI 的 `arm64` 版（需要 UEFI 固件，QEMU 官方构建自带）
3. 启动 WinApk → 新建虚拟机 → 选择镜像 → 启动。

## 开启 WHPX 硬件加速（强烈推荐）

控制面板 → 程序 → 启用或关闭 Windows 功能 → 勾选 **虚拟机平台（Virtual Machine Platform）**，重启后 QEMU 将自动使用 WHPX，性能接近原生。

## 开发

```bash
pip install -r requirements.txt
python run.py          # 运行
build.bat              # 打包 dist/WinApk.exe
```

## 架构

```
winapk/
  core/qemu.py      QEMU 探测、加速器检测、命令行构建
  core/store.py     虚拟机配置持久化（vms.json）
  core/machine.py   QProcess 运行时 + QMP 关机
  core/images.py    镜像校验、数据盘创建
  ui/               PySide6 界面
```
