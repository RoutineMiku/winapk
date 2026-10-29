# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：winapk.spec
# 用法: pyinstaller winapk.spec

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["winapk.core.qemu", "winapk.core.store", "winapk.core.machine", "winapk.core.images"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WinApk",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # GUI 应用不显示控制台
    icon=None,
)
