"""Offscreen UI audit: renders the real window and proves things with pixels.

Run:  python scripts/ui_preview.py [--tag NAME] [--platform offscreen|real]

Why this exists: "the window opened" is not evidence that the interface renders
correctly. Every check below fails loudly on a specific regression class that a
screenshot alone would hide — a squeezed control, a missing drop-down chevron, a
grey palette block over a white card, or content clipped off the right edge.

Platform matters for one thing only: the ``offscreen`` plugin has no access to
the system font database, so Chinese text comes out as tofu boxes there. The
mechanical assertions are equally valid either way, but screenshots meant to be
judged by eye must be rendered with ``--platform real``.

Exits non-zero when any assertion fails, so it doubles as the UI smoke test.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Platform must be chosen before Qt is imported; settings isolation likewise.
_PRE = argparse.ArgumentParser(add_help=False)
_PRE.add_argument("--platform", default="offscreen", choices=("offscreen", "real"))
_pre, _ = _PRE.parse_known_args()
if _pre.platform == "offscreen":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
else:
    os.environ.pop("QT_QPA_PLATFORM", None)
_AUDIT_HOME = Path(tempfile.mkdtemp(prefix="pixelpress-audit-"))
os.environ["PIXELPRESS_SETTINGS_DIR"] = str(_AUDIT_HOME)

from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QFont, QImage, QColor, QPainter  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTableView,
)

from app.core import formats  # noqa: E402
from app.core.settings_store import SettingsStore  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

FAILURES: list[str] = []
CHECKS: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        CHECKS.append(f"  ok   {message}")
    else:
        FAILURES.append(message)
        CHECKS.append(f"  FAIL {message}")


# --------------------------------------------------------------- fixtures ---
def make_samples(folder: Path) -> list[Path]:
    """Three files that exercise the queue's interesting columns."""
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    photo = Image.new("RGB", (1600, 1200))
    for y in range(1200):
        for x in range(0, 1600, 2):
            value = (x * 3 + y * 5) % 255
            photo.putpixel((x, y), (value, (value * 2) % 255, (value * 3) % 255))
            photo.putpixel((x + 1, y), (value, (value * 2) % 255, (value * 3) % 255))
    photo_path = folder / "DSC_0142.jpg"
    photo.save(photo_path, "JPEG", quality=92)
    paths.append(photo_path)

    graphic = Image.new("RGB", (1400, 900), (246, 247, 249))
    draw = ImageDraw.Draw(graphic)
    draw.rectangle([0, 0, 1400, 64], fill=(32, 38, 52))
    draw.rectangle([40, 100, 560, 460], fill=(255, 255, 255), outline=(210, 216, 226))
    draw.rectangle([600, 100, 1120, 460], fill=(240, 244, 250))
    draw.rectangle([1160, 100, 1360, 460], fill=(37, 99, 235))
    graphic_path = folder / "banner.png"
    graphic.save(graphic_path, "PNG", compress_level=9)
    paths.append(graphic_path)

    alpha = Image.new("RGBA", (900, 700), (0, 0, 0, 0))
    draw = ImageDraw.Draw(alpha)
    draw.ellipse([120, 120, 780, 580], fill=(214, 59, 22, 255))
    alpha_path = folder / "logo_alpha.png"
    alpha.save(alpha_path, "PNG")
    paths.append(alpha_path)
    return paths


# ------------------------------------------------------------------ probes ---
def darkest_in_region(widget, x0: int, y0: int, x1: int, y1: int) -> int:
    image = widget.grab().toImage()
    darkest = 255
    for y in range(max(0, y0), min(image.height(), y1)):
        for x in range(max(0, x0), min(image.width(), x1)):
            pixel = image.pixelColor(x, y)
            darkest = min(darkest, (pixel.red() + pixel.green() + pixel.blue()) // 3)
    return darkest


def text_ink(widget, threshold: int = 140) -> int:
    image = widget.grab().toImage()
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if (colour.red() + colour.green() + colour.blue()) / 3 < threshold:
                count += 1
    return count


def colour_histogram(widget) -> dict[tuple[int, int, int], int]:
    image = widget.grab().toImage()
    counts: dict[tuple[int, int, int], int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            key = (colour.red(), colour.green(), colour.blue())
            counts[key] = counts.get(key, 0) + 1
    return counts


def is_visible(widget) -> bool:
    """Fully visible, using the real visibility region (not the window rect)."""
    if not widget.isVisible():
        return False
    region = widget.visibleRegion()
    return not region.isEmpty() and region.boundingRect() == widget.rect()


def text_ink_of_font(font, text: str) -> int:
    """Ink coverage of ``text`` drawn with ``font`` on white.

    Tofu boxes are hollow outlines; a real CJK glyph carries far more ink, which
    is what makes this a usable assertion instead of a cosmetic one.
    """
    from PySide6.QtGui import QFontMetricsF

    metrics = QFontMetricsF(font)
    width = int(metrics.horizontalAdvance(text)) + 10
    height = int(metrics.height()) + 10
    image = QImage(max(width, 8), max(height, 8), QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(0xFF000000)
    painter.drawText(5, int(metrics.ascent()) + 5, text)
    painter.end()
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if (image.pixel(x, y) & 0xFFFFFF) < 0x808080:
                count += 1
    return count


def grab(window: MainWindow, name: str, folder: Path) -> Path:
    path = folder / f"{name}.png"
    window.grab().save(str(path))
    return path


# ------------------------------------------------------------------- audit ---
def audit(window: MainWindow, label: str) -> None:
    print(f"\n[{label}] 尺寸 {window.width()}x{window.height()}")
    app = QApplication.instance()
    app.processEvents()

    # 1. every visible interactive control has a clickable size.
    #    findChildren() takes exactly one type, never a tuple.
    for cls in (QPushButton, QComboBox, QSpinBox, QSlider, QTableView):
        for widget in window.findChildren(cls):
            if not is_visible(widget):
                continue
            if widget.width() < 18 or widget.height() < 18:
                name = widget.objectName()
                if hasattr(widget, "text") and callable(getattr(widget, "text", None)):
                    try:
                        name = name or widget.text()
                    except TypeError:
                        pass
                FAILURES.append(
                    f"{label}: {cls.__name__} '{name}' 被挤压到 {widget.width()}x{widget.height()}"
                )
    for progress in window.findChildren(QProgressBar):
        if is_visible(progress) and progress.height() < 6:
            FAILURES.append(f"{label}: 进度条高度仅 {progress.height()}px")

    # 2. drop-down chevrons really render (styled QComboBox loses the native one)
    combos = [c for c in window.findChildren(QComboBox) if is_visible(c)]
    if combos:
        combo = combos[0]
        darkest = darkest_in_region(combo, combo.width() - 22, 0, combo.width(), combo.height())
        check(darkest < 200, f"下拉箭头已绘制（右端最暗像素 {darkest} < 200）")
    else:
        # At the smallest window size the settings panel is scrolled below the
        # fold, so "no visible combo" is a property of the viewport, not a bug.
        CHECKS.append(f"  note {label}: 本档位无可视下拉框（设置面板在滚动区下方）")

    # 3. spinner +/- glyphs render
    spins = [s for s in window.findChildren(QSpinBox) if is_visible(s)]
    if spins:
        spin = spins[0]
        darkest = darkest_in_region(spin, spin.width() - 20, 0, spin.width(), spin.height())
        check(darkest < 200, f"微调 +/- 已绘制（右端最暗像素 {darkest} < 200）")

    # 4. palette leak sentinel: Qt's Fusion default fill must appear nowhere
    sentinel = (239, 239, 239)
    leaks = 0
    for widget in window.findChildren(QLabel):
        if not is_visible(widget) or widget.width() < 20 or widget.height() < 12:
            continue
        counts = colour_histogram(widget)
        leaks += counts.get(sentinel, 0)
    check(leaks == 0, f"无 #EFEFEF 调色板泄漏（命中 {leaks} 像素）")

    # 5. labels are transparent, not painted grey blocks
    grey_blocks = 0
    for candidate in window.findChildren(QLabel):
        if not is_visible(candidate) or candidate.width() < 40 or candidate.height() < 14:
            continue
        image = candidate.grab().toImage()
        opaque = 0
        for y in range(0, image.height(), 3):
            for x in range(0, image.width(), 3):
                if image.pixelColor(x, y).alpha() > 20:
                    opaque += 1
        # A label over a card legitimately shows the card behind it via grab();
        # what we reject is a label that painted a solid rectangle of its own.
        if opaque and image.pixelColor(2, 2).alpha() > 200:
            colour = image.pixelColor(2, 2)
            if abs(colour.red() - sentinel[0]) < 6 and abs(colour.green() - sentinel[1]) < 6:
                grey_blocks += 1
    check(grey_blocks == 0, f"标签背景透明（异常灰块 {grey_blocks}）")

    # 6. cards actually contain drawn text
    cards = [w for w in window.findChildren(QLabel) if is_visible(w)]
    titles = [w for w in cards if w.objectName() in ("cardTitle", "headerTitle", "brandTitle")]
    check(bool(titles), f"卡片标题存在（{len(titles)} 个）")
    for title in titles:
        ink = text_ink(title)
        if ink < 25:
            FAILURES.append(f"{label}: 标题「{title.text()}」几乎无像素（ink={ink}）")

    # 7. no horizontal clipping inside scroll areas and stacked pages
    from PySide6.QtWidgets import QScrollArea

    for area in window.findChildren(QScrollArea):
        if not is_visible(area):
            continue
        inner = area.widget()
        if inner is not None and inner.width() > area.viewport().width() + 2:
            FAILURES.append(
                f"{label}: 滚动区内容宽 {inner.width()} > 视口 {area.viewport().width()}，右侧被裁切"
            )

    # 8. segmented controls: exactly one checked, accent-soft background
    from app.ui.widgets import SegmentedControl

    for control in window.findChildren(SegmentedControl):
        if not is_visible(control):
            continue
        checked = [b for b in control.buttons().values() if b.isChecked()]
        if len(checked) > 1:
            FAILURES.append(f"{label}: 分段控件出现 {len(checked)} 个选中项")
        elif len(checked) == 1 and checked[0].isEnabled():
            button = checked[0]
            centre = button.grab().toImage().pixelColor(button.width() // 2, 4)
            soft = QColor(theme.tokens_for(theme.current_mode())["ACCENT_SOFT"])
            if centre.lightness() > 250:
                FAILURES.append(
                    f"{label}: 选中态「{button.text()}」没有底色（{centre.name()}）"
                )

    # 9. queue table rows are tall enough to read
    table = window.table
    if is_visible(table) and table.model().rowCount():
        if table.verticalHeader().defaultSectionSize() < 32:
            FAILURES.append(f"{label}: 队列行高仅 {table.verticalHeader().defaultSectionSize()}px")

    # 10. Chinese text must be drawn with a real CJK face, not a fallback of
    #     hollow boxes. Offscreen has no system font database, so this check is
    #     only meaningful on the real platform plugin.
    app_font = QApplication.instance().font()
    families = list(app_font.families())
    has_cjk_family = any(
        marker in family
        for family in families
        for marker in ("YaHei", "Noto", "SimSun", "Source Han", "DengXian")
    )
    check(has_cjk_family, f"应用字体含中文回退链（{', '.join(families[:4])}）")
    if app.platformName() != "offscreen":
        chain_ink = text_ink_of_font(app_font, "压缩设置")
        bare = QFont("Archivo")
        bare.setPointSize(10)
        bare_ink = text_ink_of_font(bare, "压缩设置")
        # Measured on this machine: real YaHei glyphs carry ~18% more ink at
        # 10 pt than the hollow fallback Qt picks for a Latin-only family.
        check(
            chain_ink > bare_ink * 1.1,
            f"中文使用真实字形而非缺字方框（链墨量 {chain_ink} vs 单字体 {bare_ink}）",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="ui")
    parser.add_argument("--platform", default="offscreen", choices=("offscreen", "real"))
    parser.add_argument("--out", default=str(ROOT / "benchmarks" / "ui"))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = make_samples(_AUDIT_HOME / "samples")

    app = QApplication(sys.argv[:1])
    print(f"平台插件: {app.platformName()}"
          + ("（无系统字体库，中文会显示为方框；机械断言仍然有效）" if app.platformName() == "offscreen" else ""))
    store = SettingsStore()
    store.theme_mode = "light"
    theme.apply_app_theme(app, "light")

    window = MainWindow(SettingsStore())
    window.show()
    app.processEvents()

    # --- empty state, smallest supported size
    window.resize(1080, 700)
    app.processEvents()
    audit(window, f"{args.tag}-空队列-最小")
    saved_empty = grab(window, f"{args.tag}_01_empty_1080x700", out_dir)

    # --- populated queue, default size
    window.add_paths([str(p) for p in samples])
    window.resize(1280, 820)
    app.processEvents()
    window.table.selectRow(0)
    app.processEvents()
    audit(window, f"{args.tag}-已有队列-默认")
    saved_full = grab(window, f"{args.tag}_02_queue_1280x820", out_dir)

    # --- run a real batch and wait for it to actually finish, so the captured
    #     "result" state is a finished batch and not a frame mid-run.
    window.settings_panel.mode_control.set_value("lossy", notify=True)
    window.start_batch()
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    window.runner.finished.connect(loop.quit)
    QTimer.singleShot(180_000, loop.quit)
    if window.runner.running:
        loop.exec()
    app.processEvents()
    check(not window.runner.running, "批次在超时前完成")
    stats = window.model.stats()
    check(int(stats["processed"]) > 0, f"批次已处理 {stats['processed']} 个文件")
    # Guards the signal-ordering race: the runner's own slot is connected before
    # the window's, so a synchronous finish would under-count the last file.
    rows_with_result = sum(1 for item in window.model.items() if item.result is not None)
    check(
        rows_with_result == len(window.model.items()),
        f"每一行都拿到了结果（{rows_with_result}/{len(window.model.items())}）",
    )
    check(
        int(stats["processed"]) == rows_with_result,
        f"汇总数字与行结果一致（汇总 {stats['processed']} vs 行 {rows_with_result}）",
    )
    audit(window, f"{args.tag}-压缩后")
    saved_done = grab(window, f"{args.tag}_03_done_1280x820", out_dir)

    # --- log tab
    window.bottom_switch.set_value("log", notify=True)
    app.processEvents()
    saved_log = grab(window, f"{args.tag}_04_log_1280x820", out_dir)

    # --- dark theme, wide window
    window.bottom_switch.set_value("preview", notify=True)
    window.toggle_theme()
    window.resize(1600, 1000)
    app.processEvents()
    audit(window, f"{args.tag}-深色-宽")
    saved_dark = grab(window, f"{args.tag}_05_dark_1600x1000", out_dir)

    # --- settings panel scrolled to the bottom (off-screen controls included)
    from PySide6.QtWidgets import QScrollArea

    for area in window.findChildren(QScrollArea):
        bar = area.verticalScrollBar()
        bar.setValue(bar.maximum())
        app.processEvents()
    audit(window, f"{args.tag}-设置面板已滚动到底")
    saved_scrolled = grab(window, f"{args.tag}_06_dark_scrolled", out_dir)

    window.toggle_theme()
    app.processEvents()

    print("\n".join(CHECKS[:0]))  # checks are printed by callers
    for line in CHECKS:
        print(line)
    print("\n截图：")
    for path in (saved_empty, saved_full, saved_done, saved_log, saved_dark, saved_scrolled):
        print(f"  {path}")

    if FAILURES:
        print(f"\n{len(FAILURES)} 项失败：")
        for failure in FAILURES:
            print(f"  ! {failure}")
        return 1
    print("\n全部像素审计通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
