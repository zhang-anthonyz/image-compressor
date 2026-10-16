# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PixelPress (one-dir build).

Two things to know before editing:

* ``datas`` must list every bundled resource explicitly. Fonts and the oxipng
  binary are located at run time through ``app.core.paths.app_root()``, which is
  why they land in ``assets/fonts`` and ``vendor`` next to the executable rather
  than inside the PYZ archive.
* ``excludes`` is not cosmetic. This machine has plenty of unrelated heavy
  packages installed (torch, onnxruntime, modelscope, onnx, numpy), and anything
  imported even indirectly would otherwise be collected. The engine deliberately
  needs only Pillow, pillow-heif and the standard library.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve()

# ---------------------------------------------------------------- resources ---
font_files = sorted((project_root / "app" / "assets" / "fonts").glob("*.ttf"))
license_files = sorted((project_root / "app" / "assets" / "fonts").glob("LICENSE-*.txt"))
oxipng = project_root / "vendor" / "oxipng.exe"

datas = [(str(path), "assets/fonts") for path in font_files + license_files]
if oxipng.is_file():
    datas.append((str(oxipng), "vendor"))

# ------------------------------------------------------------------ imports ---
hiddenimports = [
    "pillow_heif",
    *collect_submodules("pillow_heif"),
]

# ------------------------------------------------------------------ excludes ---
excludes = [
    # Unrelated heavy packages that happen to live in this Python environment.
    "torch", "torchvision", "torchaudio", "onnx", "onnxruntime", "onnxruntime_directml",
    "onnxscript", "modelscope", "numpy", "scipy", "pandas", "matplotlib", "sympy",
    "transformers", "huggingface_hub", "accelerate", "safetensors",
    # Development-only.
    "pytest", "iniconfig", "pluggy", "_pytest", "pygments", "IPython", "jupyter",
    "tkinter", "unittest", "pydoc_data", "lib2to3", "PyInstaller",
    # Qt modules this app never touches.
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSpatialAudio", "PySide6.QtRemoteObjects",
    "PySide6.QtStateMachine", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
    "PySide6.QtNetwork", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
]

a = Analysis(
    # The launcher, not app/main.py: PyInstaller runs the entry script as a
    # top-level module, so a file inside the package cannot use relative imports.
    [str(project_root / "PixelPress.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
# --------------------------------------------------------------- size trim ---
# Collected-but-unused binaries. PyInstaller's PySide6 hook brings Qt modules
# this app never imports, and the pillow-heif wheel ships the HEVC *encoder*
# which only matters for writing HEIC — we deliberately never do.
UNUSED_BINARIES = (
    # "libx265" is deliberately NOT trimmed: it is 22.7 MB of HEVC encoder that
    # this app never uses for encoding, but pillow-heif's libheif hard-links it,
    # so removing it silently disables all HEIC decoding. Measured, not assumed —
    # the --headless self-check reported "HEIC 不可用" when it was trimmed.
    "opengl32sw",     # 20.6 MB software OpenGL; the UI is pure raster widgets
    "qt6quick",       # not used
    "qt6qml",         # not used
    "qt6pdf",         # not used
    "qt6network",     # no networking anywhere in the app
    "qt6websockets",
    "qt6svg",
    "qt6designer",
    "qt6test",
)


def _keep_binary(entry) -> bool:
    name = Path(entry[0]).name.lower()
    return not any(marker in name for marker in UNUSED_BINARIES)


_kept = [entry for entry in a.binaries if _keep_binary(entry)]
_trimmed = len(a.binaries) - len(_kept)
a.binaries = _kept
print(f"[PixelPress.spec] trimmed {_trimmed} unused binaries")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PixelPress",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PixelPress",
)
