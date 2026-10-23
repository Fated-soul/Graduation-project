from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


ROOT = Path.cwd().resolve()
DESKTOP = ROOT / "desktop"

datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / ".streamlit"), ".streamlit"),
    (str(ROOT / "agent" / "knowledge"), "agent/knowledge"),
    (str(DESKTOP / ".env.example"), "desktop"),
]
binaries = []
hiddenimports = []

# Conda's standard-library extension modules load these DLLs from
# <base>\Library\bin. PyInstaller does not discover that directory reliably.
conda_bin = Path(sys.base_prefix) / "Library" / "bin"
for dll_name in (
    "ffi.dll",
    "libbz2.dll",
    "libcrypto-3-x64.dll",
    "libexpat.dll",
    "liblzma.dll",
    "libmpdec-4.dll",
    "libssl-3-x64.dll",
    "sqlite3.dll",
    "zlib.dll",
):
    dll_path = conda_bin / dll_name
    if dll_path.is_file():
        binaries.append((str(dll_path), "."))

for package in ("streamlit", "plotly", "reportlab", "imageio_ffmpeg"):
    datas += collect_data_files(package)

# Streamlit resolves its public version through importlib.metadata at import
# time, so its distribution metadata must be present in the frozen bundle.
datas += copy_metadata("streamlit")

hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("streamlit.runtime.scriptrunner")
hiddenimports += [
    "agent.main",
    "backend.main",
    "components.header",
    "components.sidebar",
    "pages.data_sources",
    "pages.dataset_agent",
    "pages.evidence_review",
    "pages.public_dashboard",
    "pages.research_data",
    "pages.sessions",
    "pages.subjects",
    "psycopg2._psycopg",
    "streamlit.web.cli",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

analysis = Analysis(
    [str(DESKTOP / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "frontend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "boto3",
        "botocore",
        "bokeh",
        "cv2",
        "black",
        "dask",
        "distributed",
        "docutils",
        "intake",
        "keras",
        "llvmlite",
        "matplotlib",
        "numba",
        "openpyxl",
        "panel",
        "pygame",
        "pytest",
        "qtpy",
        "scipy",
        "skimage",
        "sklearn",
        "sqlalchemy",
        "sphinx",
        "statsmodels",
        "tables",
        "tensorflow",
        "tensorflow_intel",
        "tkinter",
        "tkinter.test",
        "torch",
        "torchvision",
        "timm",
        "ultralytics",
        "unittest.test",
        "wx",
        "xarray",
        "zmq",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MingChaShuHao",
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
    icon=str(DESKTOP / "assets" / "mingcha.ico"),
    version=str(DESKTOP / "version_info.txt"),
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MingChaShuHao",
)
