# translator-app.spec
block_cipher = None

a = Analysis(
    ["translator-app/main.py"],
    pathex=["translator-app"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "win32gui", "win32con", "win32clipboard", "win32process",
        "pywintypes", "keyboard",
        "anthropic", "httpx", "certifi",
        "PyQt5.QtWidgets", "PyQt5.QtCore", "PyQt5.QtGui",
        "PyQt5.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="TranslatorApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
