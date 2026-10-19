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
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontMetrics, QImage, QColor, QPainter, QWheelEvent  # noqa: E402
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
from app.core.unit_report import saved_percent  # noqa: E402
from app.ui import fonts, theme  # noqa: E402
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
    ratio = image.devicePixelRatio() or 1.0
    x0, y0, x1, y1 = (int(x0 * ratio), int(y0 * ratio), int(x1 * ratio), int(y1 * ratio))
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


def text_ink_region(widget, x0: int, x1: int, threshold: int = 200, above: bool = False) -> int:
    """Pixels in a horizontal band on one side of ``threshold``.

    Used to prove a value is really drawn in the text area rather than being
    hidden under an overlay. Light themes count dark text; dark themes count
    light text.
    """
    image = widget.grab().toImage()
    ratio = image.devicePixelRatio() or 1.0
    x0, x1 = int(x0 * ratio), int(x1 * ratio)
    count = 0
    for y in range(image.height()):
        for x in range(max(0, x0), min(image.width(), x1)):
            colour = image.pixelColor(x, y)
            value = (colour.red() + colour.green() + colour.blue()) / 3
            if value > threshold if above else value < threshold:
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

    # 3. spinner +/- glyphs render, and the *value* is not hidden behind them.
    #    The second half is the regression that matters: QSS + NoButtons once
    #    collapsed the internal line edit to 1 px while the painted glyphs
    #    still looked fine, so a "spinner exists" assertion proved nothing.
    spins = [s for s in window.findChildren(QSpinBox) if is_visible(s)]
    surface = QColor(theme.tokens_for(theme.current_mode())["SURFACE"])
    window_image = window.grab().toImage()
    window_ratio = window_image.devicePixelRatio() or 1.0
    for spin in spins:
        edit = spin.lineEdit()
        if edit is None or edit.width() < 40:
            width = 0 if edit is None else edit.width()
            FAILURES.append(f"{label}: 数值框行编辑仅 {width}px，数值不可见")
        elif edit.textMargins().right() < 22:
            FAILURES.append(f"{label}: 数值框右侧未为 +/- 图标留出空间")
        else:
            dark = theme.current_mode() == "dark"
            value_ink = text_ink_region(
                spin,
                4,
                spin.width() - 26,
                threshold=70 if dark else 200,
                above=dark,
            )
            if value_ink < 8:
                FAILURES.append(f"{label}: 数值框内没有可读数值（ink={value_ink}）")
            else:
                CHECKS.append(
                    f"  ok   数值可见且避开 +/-（行编辑 {edit.width()}px, ink={value_ink}）"
                )
        # The value field sits beside a slider; a filled box reads as a second
        # control. Sample the *composited window* (child.grab() has no parent
        # background and comes back black) just left of the +/- strip.
        origin = spin.mapTo(window, QPoint(0, 0))
        sample = window_image.pixelColor(
            int((origin.x() + spin.width() - 26) * window_ratio),
            int((origin.y() + spin.height() / 2) * window_ratio),
        )
        delta = max(
            abs(sample.red() - surface.red()),
            abs(sample.green() - surface.green()),
            abs(sample.blue() - surface.blue()),
        )
        if delta > 4:
            FAILURES.append(
                f"{label}: 数值框仍有填充底色（{sample.name()} vs 卡片 {surface.name()}）"
            )
        else:
            CHECKS.append(f"  ok   数值框无填充底色（{sample.name()}）")
    if spins:
        spin = spins[0]
        darkest = darkest_in_region(spin, spin.width() - 20, 0, spin.width(), spin.height())
        check(darkest < 200, f"微调 +/- 已绘制（右端最暗像素 {darkest} < 200）")

    # 3b. queue columns: either they fit exactly, or a real horizontal scrollbar
    #     exposes the overflow. Clipping information without a way to reach it is
    #     the regression this check exists for.
    table = window.table
    if is_visible(table) and table.model().rowCount():
        header = table.horizontalHeader()
        total_width = sum(header.sectionSize(i) for i in range(header.count()))
        viewport_width = table.viewport().width()
        hbar = table.horizontalScrollBar()
        if total_width > viewport_width + 1:
            check(
                hbar.isVisible() and hbar.maximum() > 0,
                f"队列超宽 {total_width} > {viewport_width} 时有水平滚动条",
            )
        else:
            check(
                not hbar.isVisible(),
                f"队列适配 {total_width} ≤ {viewport_width} 时不出现水平滚动条",
            )
        savings_width = table.columnWidth(table.model().columnCount() - 1)
        check(savings_width >= 140, f"节省列宽 {savings_width}px 足以容纳条与百分比")
        result_row = next(
            (item for item in table.model().items() if item.result is not None and item.new_size),
            None,
        )
        if result_row is not None:
            text = saved_percent(result_row.original_size, result_row.new_size)
            font = fonts.make_font(size=9, mono=True, weight=fonts.WEIGHT_SEMIBOLD)
            text_width = QFontMetrics(font).horizontalAdvance(text)
            check(
                text_width + 16 <= savings_width,
                f"节省百分比「{text}」({text_width}px) 不被列宽 {savings_width}px 裁切",
            )

    # 3c. preview controls: the hint may elide, but it may not overlap the zoom
    #     cluster. ElidedLabel reports its full sentence separately.
    hint = window.preview_hint
    if is_visible(hint) and any(w.isVisible() for w in window.preview_controls):
        left_control = min(
            (w.geometry().left() for w in window.preview_controls if w.isVisible()),
            default=hint.geometry().right() + 1,
        )
        check(
            hint.geometry().right() <= left_control,
            f"预览提示不覆盖缩放控件（{hint.geometry().right()} ≤ {left_control}）",
        )

    # 3d. the comparison stage really scrolls. Fit-width must leave a vertical
    #     range for a tall photo, and 100 % must add a horizontal one; without
    #     both, the old "wide strip, no scrollbar" behaviour is back.
    view = window.preview_panel.view
    if view.has_image and is_visible(view):
        vbar = view.verticalScrollBar()
        hbar = view.horizontalScrollBar()
        check(vbar.maximum() > 0, f"预览适应宽度后可纵向滚动（范围 {vbar.maximum()}px）")
        check(vbar.isVisible(), "预览垂直滚动条可见")
        vbar.setValue(vbar.maximum())
        app.processEvents()
        check(vbar.value() == vbar.maximum(), "预览可滚动到图像底部")
        view.actual_size()
        app.processEvents()
        check(hbar.maximum() > 0, f"100% 时出现水平滚动范围（{hbar.maximum()}px）")
        check(hbar.isVisible(), "100% 时水平滚动条可见")
        view.reset_view()
        app.processEvents()
        check(view.verticalScrollBar().maximum() > 0, "适应按钮恢复可滚动的适应宽度视图")
        check(
            view.horizontalScrollBar().maximum() == 0,
            "适应宽度时没有水平滚动（滚动条出现不反噬图像宽度）",
        )
        # The hint promises a plain wheel scroll; prove the event actually
        # reaches the scroll area instead of being swallowed by the canvas.
        vbar.setValue(0)
        wheel = QWheelEvent(
            QPointF(view.viewport().width() / 2, view.viewport().height() / 2),
            QPointF(view.mapToGlobal(view.viewport().rect().center())),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(view.viewport(), wheel)
        app.processEvents()
        check(vbar.value() > 0, f"滚轮上下滚动生效（垂直位置 {vbar.value()}）")
        vbar.setValue(0)

        zoom_before = view.zoom_percent()
        ctrl_wheel = QWheelEvent(
            QPointF(view.viewport().width() / 2, view.viewport().height() / 2),
            QPointF(view.mapToGlobal(view.viewport().rect().center())),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(view.viewport(), ctrl_wheel)
        app.processEvents()
        check(view.zoom_percent() > zoom_before, "Ctrl+滚轮放大生效")
        view.reset_view()
        app.processEvents()

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
            # All three channels must be near the sentinel: the Fusion default
            # fill is neutral grey, whereas the Fluent palette's paper (#EEF3FA)
            # and dark-mode ink (#F0F4FB) both happen to sit within 6 of the
            # sentinel on red/green while differing by 11-12 on blue.
            if (
                abs(colour.red() - sentinel[0]) < 6
                and abs(colour.green() - sentinel[1]) < 6
                and abs(colour.blue() - sentinel[2]) < 6
            ):
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
            image = button.grab().toImage()
            ratio = image.devicePixelRatio() or 1.0
            centre = image.pixelColor(
                int(button.width() * ratio / 2), max(1, int(4 * ratio))
            )
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


def wait_for_finish(window: MainWindow, timeout_ms: int = 180_000) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    if not window.runner.running:
        QApplication.instance().processEvents()
        return
    loop = QEventLoop()
    window.runner.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    QApplication.instance().processEvents()


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
    window.resize(980, 640)
    app.processEvents()
    audit(window, f"{args.tag}-空队列-最小")
    saved_empty = grab(window, f"{args.tag}_01_empty_980x640", out_dir)

    # --- populated queue, default size
    window.resize(1280, 820)
    window.add_paths([str(p) for p in samples])
    app.processEvents()
    window.table.selectRow(0)
    app.processEvents()
    audit(window, f"{args.tag}-已有队列-默认")
    saved_full = grab(window, f"{args.tag}_02_queue_1280x820", out_dir)

    # --- cancel: feedback must be immediate, and the batch must still finish.
    #     (The previous runner queued every file and skipped cancelled ones
    #     without emitting, so with more files than threads it never finished.)
    window.settings_panel.mode_control.set_value("lossy", notify=True)
    window.toast.hide()  # the add-files toast is stale once the batch starts
    window.start_batch()
    check(window.runner.running, "批次已开始")
    check(window.task_panel.state() == "running", "运行时任务卡进入「运行中」状态")
    check(
        window.task_panel.cancel_button.isVisible() and window.task_panel.cancel_button.isEnabled(),
        "运行时取消按钮可见且可用",
    )
    check(window.task_panel.start_button.text() == "压缩中…", "运行时开始按钮文案切换为压缩中")
    check(window.task_panel.state_badge.text() == "运行中", "运行时状态徽标明确")
    check(not window.add_files_button.isEnabled(), "运行时队列编辑按钮禁用")
    check(not window.select_all_button.isEnabled(), "运行时全选按钮禁用")
    saved_running = grab(window, f"{args.tag}_03_running_1280x820", out_dir)
    window._request_cancel()
    check(window.task_panel.state() == "cancelling", "点击取消后立即进入「正在取消」状态")
    check(not window.task_panel.cancel_button.isEnabled(), "取消中按钮已禁用，避免重复点击")
    check(window.task_panel.cancel_button.text() == "正在取消…", "取消按钮文案切换为正在取消")
    check("正在取消" in window.task_panel.status_label.text(), "状态区明确提示正在取消")
    saved_cancelling = grab(window, f"{args.tag}_03_cancelling_1280x820", out_dir)
    wait_for_finish(window)
    check(not window.runner.running, "取消后批次正常结束，没有挂起")
    check(window.task_panel.state() == "cancelled", "取消后任务卡进入「已取消」状态")
    check(window.task_panel.start_button.isEnabled(), "取消后开始按钮恢复可用")
    check(window.add_files_button.isEnabled(), "取消后队列编辑按钮恢复")
    check("已取消" in window.task_panel.status_label.text(), "取消结果在状态区可见")
    check("已取消" in window.task_panel.state_badge.text(), "取消结果在徽标可见")
    check("已取消" in window.status_text.full_text(), "取消结果在底部状态栏可见")
    window.table.selectRow(0)
    app.processEvents()

    # --- run a real batch to completion, so the captured "result" state is a
    #     finished batch and not a frame mid-run.
    window.start_batch()
    wait_for_finish(window)
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

    # --- narrow window: the queue must admit its overflow with a scrollbar and
    #     the settings rail must still be usable.
    window.resize(980, 640)
    app.processEvents()
    audit(window, f"{args.tag}-窄窗")
    saved_narrow = grab(window, f"{args.tag}_04_done_980x640", out_dir)

    # --- log tab at the default size
    window.resize(1280, 820)
    window.bottom_switch.set_value("log", notify=True)
    app.processEvents()
    saved_log = grab(window, f"{args.tag}_05_log_1280x820", out_dir)

    # --- dark theme, wide window
    window.bottom_switch.set_value("preview", notify=True)
    window.toggle_theme()
    window.resize(1600, 1000)
    app.processEvents()
    audit(window, f"{args.tag}-深色-宽")
    saved_dark = grab(window, f"{args.tag}_06_dark_1600x1000", out_dir)

    # --- large full screen
    window.resize(1920, 1080)
    app.processEvents()
    audit(window, f"{args.tag}-深色-大屏")
    saved_large = grab(window, f"{args.tag}_07_dark_1920x1080", out_dir)

    # --- settings panel scrolled to the bottom (off-screen controls included)
    window.resize(1600, 1000)
    app.processEvents()
    from PySide6.QtWidgets import QScrollArea

    for area in window.findChildren(QScrollArea):
        bar = area.verticalScrollBar()
        bar.setValue(bar.maximum())
        app.processEvents()
    audit(window, f"{args.tag}-设置面板已滚动到底")
    saved_scrolled = grab(window, f"{args.tag}_08_dark_scrolled", out_dir)

    window.toggle_theme()
    app.processEvents()

    for line in CHECKS:
        print(line)
    print("\n截图：")
    for path in (
        saved_empty,
        saved_full,
        saved_running,
        saved_cancelling,
        saved_done,
        saved_narrow,
        saved_log,
        saved_dark,
        saved_large,
        saved_scrolled,
    ):
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
