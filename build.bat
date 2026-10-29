@echo off
rem 构建 WinApk.exe（单文件）
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean winapk.spec
echo.
echo 构建完成: %~dp0dist\WinApk.exe
pause
