from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(project_root / "app" / "prompts" / "assets"), "app/prompts/assets"),
]

frontend_dist = project_root / "frontend" / "dist"
if frontend_dist.exists():
    datas.append((str(frontend_dist), "frontend/dist"))

hiddenimports = collect_submodules("uvicorn")


a = Analysis(
    [str(project_root / "app" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StatefulInterviewAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StatefulInterviewAgent",
)
