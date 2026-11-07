# -*- mode: python ; coding: utf-8 -*-
# FileVerifyRename 打包配置（PyInstaller，onedir 目录模式）
#
# 产物：dist\文件校验重命名工具\  →  交由 installer.iss 压成安装包
# 用法：在仓库根目录执行  pyinstaller FileVerifyRename.spec
#       或直接双击 build.bat（会自动挑带 tkinter 的解释器）
#
# 注意：本文件是 onedir 模式。若只想出单文件版，用命令行
#       pyinstaller -F -w -n 文件校验重命名工具 --icon assets/logo.ico ^
#                   --add-data "assets/logo.ico;." main.py

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/logo.ico', '.')],   # 图标随包分发到 exe 同级目录
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='文件校验重命名工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='文件校验重命名工具',
)
