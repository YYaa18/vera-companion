# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 exe，内含启动器与陪玩助手。

    pyinstaller build.spec --noconfirm

产物: dist/VeraLauncher.exe
    VeraLauncher.exe              启动器
    VeraLauncher.exe --assistant  陪玩助手（由启动器拉起）
"""
import os

block_cipher = None

# 人设文件随 exe 一起打包，运行时从 _MEIPASS/personas 读。
# PyInstaller 以 spec 所在目录为工作目录，所以相对路径即可。
persona_files = []
_pdir = "personas"
if os.path.isdir(_pdir):
    for _fn in sorted(os.listdir(_pdir)):
        if _fn.endswith(".txt"):
            persona_files.append((os.path.join(_pdir, _fn), "personas"))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=persona_files + [
        ("persona_voice.txt", "."),
        ("persona.txt", "."),
    ],
    hiddenimports=[
        "launcher",
        "voice_companion",
        "speech_bubble",
        "pet_window",
        "pet_widget",
        "game_state",
        "cheat_actions",
        "ai_peer",
        "ai_dialogue",
        "persona_power",
        "room_map",
        "voice",
        "config",
        "personas",
        "mss",
        "win32gui",
        "win32con",
        "win32ui",
        "pywintypes",
        "sounddevice",
        "numpy",
        "PIL.Image",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas", "pytest",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia", "PySide6.QtQuick3D", "PySide6.QtBluetooth",
        "PySide6.QtPositioning", "PySide6.QtSerialPort", "PySide6.QtSql",
        "PySide6.QtTest", "PySide6.QtOpenGL", "PySide6.QtDesigner",
        "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="VeraLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
