# PyInstaller build spec — produces a single dist/typelessless.exe on Windows.
#   pip install -e ".[build]"
#   pyinstaller --noconfirm --clean typelessless.spec
#
# Uses collect_all on the packages that ship data files / dynamic libs / pick a
# platform backend at runtime, so the one-file exe is self-contained.

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = [], [], []

for pkg in (
    "sounddevice",   # bundles the PortAudio DLL
    "pynput",        # keyboard backend chosen at runtime
    "pystray",       # tray backend chosen at runtime
    "PIL",
    "anthropic",
    "websockets",
    "pyperclip",
    "certifi",       # CA bundle for https (anthropic/httpx)
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Some libraries read their own version via importlib.metadata at import time.
for pkg in ("anthropic", "pydantic"):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# Windows backends aren't always detected by static analysis.
hiddenimports += [
    "pystray._win32",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

a = Analysis(
    ["src/typelessless/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="typelessless",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # shows a log window; set False and rebuild once you trust it
    disable_windowed_traceback=False,
    icon=None,
)
