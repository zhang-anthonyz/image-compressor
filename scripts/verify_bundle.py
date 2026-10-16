"""Acceptance step 1: prove what the frozen build contains, from the TOC files.

Run BEFORE deleting build/ — Analysis-00.toc, PYZ-00.toc and COLLECT-00.toc all
disappear with it, and they are the most direct evidence of what was collected.

Layout note: PyInstaller 6 collects everything into ``dist/<app>/_internal/``, so
resource paths must be checked there (PyInstaller 5 put them beside the exe).

Run:  python scripts/verify_bundle.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "PixelPress"
INTERNAL = DIST / "_internal"
BUILD = ROOT / "build" / "PixelPress"

MUST_PRESENT_MODULES = [
    "app.ui.queue_model", "app.ui.preview", "app.ui.panels", "app.ui.widgets",
    "app.ui.fonts", "app.ui.theme", "app.ui.workers", "app.ui.icons",
    "app.ui.main_window", "app.ui.ui_logic",
    "app.core.encoders.oxipng_encoder", "app.core.encoders.pillow_encoder",
    "app.core.encoders.registry", "app.core.pipeline", "app.core.naming",
    "app.core.settings_store", "app.core.planner", "app.core.formats",
    "app.core.imaging", "app.core.paths", "app.core.unit_report",
    "pillow_heif", "PIL.Image", "PIL.AvifImagePlugin",
]

#: Packages that must NOT be in the bundle, matched against collected file paths.
MUST_BE_ABSENT = ["torch", "onnxruntime", "onnx", "modelscope", "numpy", "scipy", "pytest"]

EXPECTED_FONTS = {
    "Archivo-Variable.ttf", "IBMPlexMono-Regular.ttf",
    "IBMPlexMono-Medium.ttf", "IBMPlexMono-SemiBold.ttf",
}


def main() -> int:
    failures: list[str] = []
    print("=== 1a. 入包证据（TOC 模块点分名）===")
    toc_blob = ""
    for name in ("Analysis-00.toc", "PYZ-00.toc", "COLLECT-00.toc"):
        path = BUILD / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            toc_blob += text
            print(f"  {name}: {len(text.splitlines())} 行")
        else:
            failures.append(f"缺少 {name}")
    # Normalise: TOC entries are repr-formatted tuples with escaped separators.
    flat = toc_blob.replace("\\\\", "/").replace("\\", "/")
    for module in MUST_PRESENT_MODULES:
        hit = module in flat or module.replace(".", "/") in flat
        print(f"  {'ok  ' if hit else 'FAIL'} {module}")
        if not hit:
            failures.append(f"模块未入包: {module}")

    print("\n=== 1b. 排除项确实不在产物里 ===")
    # COLLECT-00.toc lists the files that actually land in dist/. The Analysis TOC
    # also mentions hook search paths (e.g. numpy/_pyinstaller), which is not
    # evidence that the package itself was collected.
    collect_toc = BUILD / "COLLECT-00.toc"
    collected_paths = ""
    if collect_toc.is_file():
        collected_paths = collect_toc.read_text(encoding="utf-8", errors="ignore")
        collected_paths = collected_paths.replace("\\\\", "/").replace("\\", "/")
    for package in MUST_BE_ABSENT:
        marker = f"site-packages/{package}/"
        present = marker in collected_paths
        print(f"  {'WARN' if present else 'ok  '} {package} {'仍被收集' if present else '未入包'}")
        if present:
            failures.append(f"排除失败: {package}")

    print("\n=== 1b2. 大体积二进制的裁剪结果 ===")
    for marker, should_be_present, why in (
        ("opengl32sw", False, "纯栅格界面，不需要软件 OpenGL 回退"),
        ("Qt6Quick", False, "未使用"),
        ("Qt6Qml", False, "未使用"),
        ("Qt6Pdf", False, "未使用"),
        ("libx265", True, "libheif 硬依赖它，裁掉会导致 HEIC 解码失效（实测）"),
    ):
        present = any(marker.lower() in path.name.lower() for path in DIST.rglob("*"))
        ok = present == should_be_present
        state = "保留" if present else "已裁剪"
        print(f"  {'ok  ' if ok else 'FAIL'} {marker}: {state}（{why}）")
        if not ok:
            failures.append(
                f"{marker} 状态错误：{'应保留' if should_be_present else '应裁剪'}，实际{state}"
            )

    print("\n=== 1c. 资源落地 ===")
    font_dir = INTERNAL / "assets" / "fonts"
    bundled_fonts = {path.name for path in font_dir.glob("*.ttf")} if font_dir.is_dir() else set()
    missing_fonts = EXPECTED_FONTS - bundled_fonts
    print(f"  _internal/assets/fonts: {len(bundled_fonts)} 个 ttf"
          + (f"，缺少 {sorted(missing_fonts)}" if missing_fonts else "（齐全）"))
    if missing_fonts:
        failures.append(f"字体缺失: {sorted(missing_fonts)}")
    licenses = list(font_dir.glob("LICENSE-*.txt")) if font_dir.is_dir() else []
    print(f"  OFL 许可文件: {len(licenses)} 个")
    if not licenses:
        failures.append("OFL 许可未随包")

    oxipng = INTERNAL / "vendor" / "oxipng.exe"
    print(f"  _internal/vendor/oxipng.exe: "
          f"{oxipng.stat().st_size / 1024:.0f} KB" if oxipng.is_file() else "  缺失")
    if not oxipng.is_file():
        failures.append("oxipng 未随包")

    heif_dlls = sorted(path.name.split("-")[0] for path in INTERNAL.glob("libheif*.dll"))
    print(f"  HEIC 解码依赖: {heif_dlls or '缺失'}")
    if not heif_dlls:
        failures.append("libheif 未随包")

    print("\n=== 1d. 产物体积 ===")
    exe = DIST / "PixelPress.exe"
    files = [path for path in DIST.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    print(f"  PixelPress.exe: {exe.stat().st_size / 1e6:.2f} MB" if exe.is_file() else "  exe 缺失")
    print(f"  目录总计: {total / 1e6:.1f} MB / {len(files)} 个文件")
    if not exe.is_file():
        failures.append("exe 缺失")

    print("\n" + ("全部通过" if not failures else "失败:\n  " + "\n  ".join(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
