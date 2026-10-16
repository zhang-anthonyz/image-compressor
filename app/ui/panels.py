"""The four panels that make up the workspace.

Each panel owns its controls and knows nothing about compression: it renders a
plan and reports intent. That separation is what keeps the settings panel
testable through ``plan()`` / ``apply_plan()`` without a running batch.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core import task_log
from ..core.formats import FormatSpec
from ..core.planner import CompressionPlan, Effort, MetadataPolicy, NamingPolicy, clamp_quality, clamp_scale
from ..core.unit_report import human_size
from . import fonts, icons, theme, ui_logic
from .preview import CompareView, load_pixmap
from .widgets import (
    ChevronComboBox,
    IconButton,
    MicroLabel,
    MonoLabel,
    PlusMinusSpinBox,
    SegmentedControl,
    TaskSummary,
    divider,
    make_card,
)


def _form_label(text: str, tooltip: str = "") -> QLabel:
    """Form labels are real widgets so their typography is under our control."""
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    if tooltip:
        label.setToolTip(tooltip)
    return label


def _populate(combo: ChevronComboBox, options: list[tuple[str, str]], current: str) -> None:
    combo.clear()
    for value, label in options:
        combo.addItem(label, value)
    index = combo.findData(current)
    if index >= 0:
        combo.setCurrentIndex(index)


# =============================================================== settings ===
class SettingsPanel(QFrame):
    """The compression settings card."""

    changed = Signal()

    def __init__(self, plan: CompressionPlan, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plan = plan
        self._loading = False
        self._context_key: str | None = None
        self._context_size: tuple[int, int] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        card, body = make_card(
            "压缩设置",
            "改动立即生效；正在压缩时，调整会在下一批应用。",
            eyebrow="SETTINGS",
            parent=self,
        )
        outer.addWidget(card)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        body.addLayout(form)

        # ---- mode
        self.mode_control = SegmentedControl(
            [(ui_logic.MODE_LOSSLESS, "无损"), (ui_logic.MODE_LOSSY, "有损")]
        )
        self.mode_control.set_value(plan.mode.value)
        form.addRow(_form_label("模式", "无损：像素与压缩前一致；有损：牺牲画质换体积"), self.mode_control)

        # ---- quality
        quality_row = QHBoxLayout()
        quality_row.setSpacing(9)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(plan.quality)
        self.quality_slider.setMinimumWidth(120)
        self.quality_spin = PlusMinusSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(plan.quality)
        self.quality_spin.setFixedWidth(74)
        quality_row.addWidget(self.quality_slider, 1)
        quality_row.addWidget(self.quality_spin)
        quality_widget = QWidget()
        quality_widget.setLayout(quality_row)
        form.addRow(_form_label("质量", "1–100；各格式标尺不同，下方提示按当前格式换算"), quality_widget)

        self.preset_control = SegmentedControl(ui_logic.QUALITY_PRESET_OPTIONS)
        form.addRow(_form_label("预设"), self.preset_control)

        self.quality_hint = QLabel("")
        self.quality_hint.setObjectName("cardHint")
        self.quality_hint.setWordWrap(True)
        body.addWidget(self.quality_hint)

        self.note_label = QLabel("")
        self.note_label.setObjectName("noteLabel")
        self.note_label.setWordWrap(True)
        self.note_label.hide()
        body.addWidget(self.note_label)

        body.addWidget(divider())

        # ---- scale
        scale_row = QHBoxLayout()
        scale_row.setSpacing(9)
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(5, 100)
        self.scale_slider.setValue(int(plan.scale_percent))
        self.scale_spin = PlusMinusSpinBox()
        self.scale_spin.setRange(5, 100)
        self.scale_spin.setValue(int(plan.scale_percent))
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setFixedWidth(80)
        scale_row.addWidget(self.scale_slider, 1)
        scale_row.addWidget(self.scale_spin)
        scale_widget = QWidget()
        scale_widget.setLayout(scale_row)
        form.addRow(_form_label("缩放", "按百分比等比缩放，纵横比始终锁定"), scale_widget)

        self.scale_presets = SegmentedControl(
            [(str(value), label) for label, value in ui_logic.SCALE_PRESETS]
        )
        form.addRow(_form_label("快捷"), self.scale_presets)

        self.scale_readout = MonoLabel("→ 尺寸未知")
        self.scale_readout.setObjectName("cardHint")
        self.scale_readout.setWordWrap(True)
        body.addWidget(self.scale_readout)

        body.addWidget(divider())

        # ---- format / metadata
        self.format_combo = ChevronComboBox()
        self.format_combo.setSizeAdjustPolicy(ChevronComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.format_combo.setMinimumContentsLength(10)
        self.format_combo.setMinimumHeight(30)
        _populate(self.format_combo, ui_logic.format_options(), ui_logic.KEEP_FORMAT_VALUE)
        form.addRow(_form_label("输出格式", "保持原格式时不会改变文件类型"), self.format_combo)

        self.metadata_combo = ChevronComboBox()
        self.metadata_combo.setMinimumHeight(30)
        _populate(self.metadata_combo, ui_logic.metadata_options(), plan.metadata.value)
        form.addRow(_form_label("元数据", "方向始终写入像素，不会出现旋转错乱"), self.metadata_combo)

        self.format_note = QLabel("")
        self.format_note.setObjectName("cardHint")
        self.format_note.setWordWrap(True)
        body.addWidget(self.format_note)

        body.addWidget(divider())

        # ---- output
        output_row = QHBoxLayout()
        output_row.setSpacing(6)
        self.out_dir_edit = QLineEdit()
        self.out_dir_edit.setPlaceholderText("默认：源文件目录 / compressed")
        self.out_dir_edit.setMinimumHeight(30)
        self.browse_button = QPushButton("选择")
        self.browse_button.setObjectName("softButton")
        self.browse_button.setMinimumHeight(30)
        self.open_dir_button = IconButton("open-folder", "打开输出目录", size=30)
        output_row.addWidget(self.out_dir_edit, 1)
        output_row.addWidget(self.browse_button)
        output_row.addWidget(self.open_dir_button)
        output_widget = QWidget()
        output_widget.setLayout(output_row)
        form.addRow(_form_label("输出目录"), output_widget)

        # Stacked, not side by side: two full-sentence checkboxes on one line need
        # ~270 px, which would raise the card's minimum width above the settings
        # column and clip its right edge.
        self.keep_smaller_check = QCheckBox("无收益时保留原文件")
        self.keep_smaller_check.setChecked(plan.keep_smaller)
        self.keep_smaller_check.setToolTip("压缩结果反而更大时，直接沿用原文件")
        self.inplace_check = QCheckBox("原地覆盖源文件")
        self.inplace_check.setChecked(plan.inplace)
        self.inplace_check.setToolTip("危险：直接改写源文件；开启后需二次确认，且不能同时转换格式")
        checks_widget = QWidget()
        checks = QVBoxLayout(checks_widget)
        checks.setContentsMargins(0, 0, 0, 0)
        checks.setSpacing(5)
        checks.addWidget(self.keep_smaller_check)
        checks.addWidget(self.inplace_check)
        form.addRow(_form_label(""), checks_widget)

        # ---- naming
        naming_row = QHBoxLayout()
        naming_row.setSpacing(6)
        self.naming_combo = ChevronComboBox()
        self.naming_combo.setMinimumHeight(30)
        _populate(self.naming_combo, ui_logic.naming_options(), plan.naming.value)
        self.naming_combo.setFixedWidth(126)
        self.naming_value_edit = QLineEdit(plan.suffix)
        self.naming_value_edit.setMinimumHeight(30)
        naming_row.addWidget(self.naming_combo)
        naming_row.addWidget(self.naming_value_edit, 1)
        naming_widget = QWidget()
        naming_widget.setLayout(naming_row)
        form.addRow(_form_label("命名"), naming_widget)

        self.collision_combo = ChevronComboBox()
        self.collision_combo.setMinimumHeight(30)
        _populate(self.collision_combo, ui_logic.collision_options(), plan.collision.value)
        form.addRow(_form_label("同名冲突"), self.collision_combo)

        self.naming_preview = MonoLabel("photo_min.jpg")
        self.naming_preview.setObjectName("cardHint")
        # Long file names must wrap rather than widen the whole settings column:
        # an unwrapped label raises the panel's minimum width and the scroll area
        # then clips the card's right edge.
        self.naming_preview.setWordWrap(True)
        body.addWidget(self.naming_preview)

        body.addWidget(divider())

        # ---- effort
        self.effort_control = SegmentedControl(ui_logic.effort_options())
        self.effort_control.set_value(plan.effort.value)
        form.addRow(_form_label("力度", "快速更省时间，极致更省体积"), self.effort_control)

        workers_row = QHBoxLayout()
        workers_row.setSpacing(6)
        self.workers_spin = PlusMinusSpinBox()
        self.workers_spin.setRange(0, 32)
        self.workers_spin.setValue(plan.workers)
        self.workers_spin.setFixedWidth(74)
        workers_hint = QLabel("0 = 自动（最多 4 线程）")
        workers_hint.setObjectName("cardHint")
        workers_row.addWidget(self.workers_spin)
        workers_row.addWidget(workers_hint, 1)
        workers_widget = QWidget()
        workers_widget.setLayout(workers_row)
        form.addRow(_form_label("线程"), workers_widget)

        body.addStretch(1)

        # ---- wiring
        self.mode_control.changed.connect(self._on_mode)
        self.preset_control.changed.connect(self._on_preset)
        self.scale_presets.changed.connect(self._on_scale_preset)
        self.effort_control.changed.connect(lambda _: self._emit())
        self.quality_slider.valueChanged.connect(self._on_quality_slider)
        self.quality_spin.valueChanged.connect(self._on_quality_spin)
        self.scale_slider.valueChanged.connect(self._on_scale_slider)
        self.scale_spin.valueChanged.connect(self._on_scale_spin)
        self.format_combo.currentIndexChanged.connect(self._on_format)
        self.metadata_combo.currentIndexChanged.connect(lambda _: self._emit())
        self.collision_combo.currentIndexChanged.connect(lambda _: self._emit())
        self.naming_combo.currentIndexChanged.connect(self._on_naming)
        self.naming_value_edit.textChanged.connect(self._on_naming_text)
        self.keep_smaller_check.toggled.connect(lambda _: self._emit())
        self.inplace_check.toggled.connect(self._on_inplace)
        self.workers_spin.valueChanged.connect(lambda _: self._emit())
        self.out_dir_edit.textChanged.connect(lambda _: self._emit())
        self.browse_button.clicked.connect(self._choose_output_dir)
        self.format_combo.view().setMinimumWidth(220)

        self._sync_from_plan()

    # ------------------------------------------------------------- read/write
    def plan(self) -> CompressionPlan:
        """Current settings as a plan (the widget layer holds no other state)."""
        plan = self._plan.copy()
        plan.mode = ui_logic.Mode(self.mode_control.value() or ui_logic.MODE_LOSSY)
        plan.quality = clamp_quality(self.quality_spin.value())
        plan.scale_percent = clamp_scale(self.scale_spin.value())
        target = self.format_combo.currentData()
        plan.target_format = None if target in (None, "", ui_logic.KEEP_FORMAT_VALUE) else str(target)
        plan.metadata = MetadataPolicy(self.metadata_combo.currentData())
        plan.naming = NamingPolicy(self.naming_combo.currentData())
        text = self.naming_value_edit.text()
        if plan.naming is NamingPolicy.SUFFIX:
            plan.suffix = text
        elif plan.naming is NamingPolicy.PREFIX:
            plan.prefix = text
        else:
            plan.template = text
        from ..core.planner import CollisionPolicy

        plan.collision = CollisionPolicy(self.collision_combo.currentData())
        plan.effort = Effort(self.effort_control.value() or Effort.BALANCED.value)
        plan.keep_smaller = self.keep_smaller_check.isChecked()
        plan.inplace = self.inplace_check.isChecked()
        plan.workers = int(self.workers_spin.value())
        plan.out_dir = self.out_dir_edit.text().strip() or None
        return plan

    def apply_plan(self, plan: CompressionPlan) -> None:
        self._loading = True
        try:
            self.mode_control.set_value(plan.mode.value)
            self.quality_slider.setValue(plan.quality)
            self.quality_spin.setValue(plan.quality)
            self.scale_slider.setValue(int(plan.scale_percent))
            self.scale_spin.setValue(int(plan.scale_percent))
            target = plan.target_format or ui_logic.KEEP_FORMAT_VALUE
            index = self.format_combo.findData(target)
            self.format_combo.setCurrentIndex(max(0, index))
            self.metadata_combo.setCurrentIndex(max(0, self.metadata_combo.findData(plan.metadata.value)))
            self.naming_combo.setCurrentIndex(max(0, self.naming_combo.findData(plan.naming.value)))
            self.collision_combo.setCurrentIndex(max(0, self.collision_combo.findData(plan.collision.value)))
            self.effort_control.set_value(plan.effort.value)
            self.keep_smaller_check.setChecked(plan.keep_smaller)
            self.inplace_check.setChecked(plan.inplace)
            self.workers_spin.setValue(plan.workers)
            self.out_dir_edit.setText(plan.out_dir or "")
        finally:
            self._loading = False
        self._plan = plan
        self._sync_from_plan()

    def set_context(self, source_key: str | None, source_size: tuple[int, int] | None) -> None:
        """Tell the panel which file the settings currently describe."""
        self._context_key = source_key
        self._context_size = source_size
        self._sync_from_plan()

    def set_running(self, running: bool) -> None:
        for widget in (
            self.mode_control, self.preset_control, self.scale_presets, self.effort_control,
            self.quality_slider, self.quality_spin, self.scale_slider, self.scale_spin,
            self.format_combo, self.metadata_combo, self.naming_combo, self.naming_value_edit,
            self.collision_combo, self.keep_smaller_check, self.inplace_check,
            self.workers_spin, self.out_dir_edit, self.browse_button,
        ):
            if isinstance(widget, SegmentedControl):
                for button in widget.buttons().values():
                    button.setEnabled(not running)
            else:
                widget.setEnabled(not running)
        if not running:
            self._sync_from_plan()

    def set_out_dir(self, text: str) -> None:
        self.out_dir_edit.setText(text)

    # ------------------------------------------------------------- reactions
    def _emit(self) -> None:
        if self._loading:
            return
        self._sync_from_plan()
        self.changed.emit()

    def _on_mode(self, value: str) -> None:
        self._sync_from_plan()
        self._emit()

    def _on_preset(self, value: str) -> None:
        quality = ui_logic.quality_value_from_preset(value)
        if quality is None:
            return
        self._loading = True
        self.quality_slider.setValue(quality)
        self.quality_spin.setValue(quality)
        self._loading = False
        self._emit()

    def _on_scale_preset(self, value: str) -> None:
        try:
            percent = int(value)
        except ValueError:
            return
        self._loading = True
        self.scale_slider.setValue(percent)
        self.scale_spin.setValue(percent)
        self._loading = False
        self._emit()

    def _on_quality_slider(self, value: int) -> None:
        self._loading = True
        self.quality_spin.setValue(value)
        self._loading = False
        self._emit()

    def _on_quality_spin(self, value: int) -> None:
        self._loading = True
        self.quality_slider.setValue(value)
        self._loading = False
        self._emit()

    def _on_scale_slider(self, value: int) -> None:
        self._loading = True
        self.scale_spin.setValue(value)
        self._loading = False
        self._emit()

    def _on_scale_spin(self, value: int) -> None:
        self._loading = True
        self.scale_slider.setValue(value)
        self._loading = False
        self._emit()

    def _on_format(self, _index: int) -> None:
        self._sync_from_plan()
        self._emit()

    def _on_naming(self, _index: int) -> None:
        policy = NamingPolicy(self.naming_combo.currentData())
        self._loading = True
        if policy is NamingPolicy.SUFFIX:
            self.naming_value_edit.setText(self._plan.suffix)
        elif policy is NamingPolicy.PREFIX:
            self.naming_value_edit.setText(self._plan.prefix)
        else:
            self.naming_value_edit.setText(self._plan.template)
        self._loading = False
        self._emit()

    def _on_naming_text(self, _text: str) -> None:
        self._emit()

    def _on_inplace(self, checked: bool) -> None:
        if checked and self.format_combo.currentData() not in (ui_logic.KEEP_FORMAT_VALUE, None, ""):
            self._loading = True
            self.format_combo.setCurrentIndex(self.format_combo.findData(ui_logic.KEEP_FORMAT_VALUE))
            self._loading = False
        self._sync_from_plan()
        self._emit()

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.out_dir_edit.text() or "")
        if directory:
            self.out_dir_edit.setText(directory)

    # ------------------------------------------------------------------ sync
    def _sync_from_plan(self) -> None:
        """Re-derive every enabled state and hint from the current values."""
        plan = self.plan()
        target = ui_logic.effective_target(self._context_key, plan.target_format)
        availability = ui_logic.mode_availability(target)

        for mode, (allowed, reason) in availability.items():
            self.mode_control.set_options_enabled({mode: allowed})
            if reason:
                self.mode_control.set_disabled_reason(mode, reason)

        current_mode = plan.mode.value
        allowed, reason = availability.get(current_mode, (True, ""))
        if not allowed:
            fallback = ui_logic.MODE_LOSSY if current_mode == ui_logic.MODE_LOSSLESS else ui_logic.MODE_LOSSLESS
            if availability.get(fallback, (False, ""))[0]:
                self._loading = True
                self.mode_control.set_value(fallback)
                self._loading = False
                plan.mode = ui_logic.Mode(fallback)
                current_mode = fallback

        has_quality = ui_logic.quality_applies(current_mode, target)
        self.quality_slider.setEnabled(has_quality)
        self.quality_spin.setEnabled(has_quality)
        self.preset_control.setVisible(has_quality)

        if has_quality:
            self.quality_hint.setText(ui_logic.quality_hint(target, current_mode, plan.quality))
        else:
            self.quality_hint.setText(ui_logic.quality_hint(target, current_mode, plan.quality))

        self.note_label.setVisible(bool(reason))
        if reason:
            self.note_label.setText(reason)

        self.scale_readout.setText(ui_logic.scale_readout(plan.scale_percent, self._context_size))
        self.naming_preview.setText(
            "示例：" + ui_logic.naming_preview(plan, "photo.jpg", target)
        )

        # In-place overwrite cannot coexist with a format change.
        if plan.inplace:
            self.format_combo.setEnabled(False)
            self.format_combo.setToolTip("原地覆盖时必须保持原格式")
            self.out_dir_edit.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.open_dir_button.setEnabled(False)
        else:
            self.format_combo.setEnabled(True)
            self.format_combo.setToolTip("")
            self.out_dir_edit.setEnabled(True)
            self.browse_button.setEnabled(True)
            self.open_dir_button.setEnabled(True)

        preset = ui_logic.preset_for_quality(plan.quality)
        if preset:
            self.preset_control.set_value(preset)
        text = (
            plan.suffix if plan.naming is NamingPolicy.SUFFIX
            else plan.prefix if plan.naming is NamingPolicy.PREFIX
            else plan.template
        )
        if self.naming_value_edit.text() != text:
            self._loading = True
            self.naming_value_edit.setText(text)
            self._loading = False


# =================================================================== task ===
class TaskPanel(QFrame):
    """Run controls, live progress and the post-batch summary."""

    startRequested = Signal()
    cancelRequested = Signal()
    openOutputRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card, body = make_card("任务", eyebrow="RUN", parent=self)
        outer.addWidget(card)

        self.summary = TaskSummary()
        body.addWidget(self.summary)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setProperty("state", "idle")
        body.addWidget(self.progress)

        self.status_label = QLabel("队列为空")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        body.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.open_button = QPushButton("打开输出目录")
        self.open_button.setObjectName("softButton")
        self.open_button.setEnabled(False)
        self.start_button = QPushButton("开始压缩")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setIcon(icons.icon("play", theme.tokens_for("light")["ACCENT_ON"], 16))
        self.start_button.setIconSize(QSize(15, 15))
        self.start_button.setEnabled(False)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.start_button)
        body.addLayout(buttons)

        self.start_button.clicked.connect(self.startRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.open_button.clicked.connect(self.openOutputRequested.emit)

    def set_ready(self, ready: bool, count: int, running: bool) -> None:
        self.start_button.setEnabled(ready and not running)
        self.cancel_button.setEnabled(running)
        if not running and not ready:
            self.status_label.setText("队列为空 · 添加图片后即可开始")
            self.summary.show_idle()
            self.progress.setValue(0)

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running and self.start_button.isEnabled())
        self.cancel_button.setEnabled(running)

    def set_status_text(self, text: str) -> None:
        self.status_label.setText(text)

    def show_progress(self, done: int, total: int, saved: int) -> None:
        self.progress.setValue(int(1000 * done / total) if total else 0)
        self.summary.show_progress(done, total, saved)

    def show_result(self, total: int, saved: int, ratio: float, duration: str, failures: int) -> None:
        self.progress.setValue(1000)
        self.progress.setProperty("state", "failed" if failures else "done")
        self._repolish(self.progress)
        self.summary.show_result(total, saved, ratio, duration, failures)
        self.open_button.setEnabled(True)

    def show_cancelled(self, done: int, total: int) -> None:
        self.progress.setProperty("state", "idle")
        self._repolish(self.progress)
        self.summary.show_cancelled(done, total)

    def reset(self) -> None:
        self.progress.setValue(0)
        self.progress.setProperty("state", "idle")
        self._repolish(self.progress)
        self.summary.show_idle()
        self.open_button.setEnabled(False)

    def refresh_icons(self) -> None:
        tokens = theme.tokens_for(theme.current_mode())
        self.start_button.setIcon(icons.icon("play", tokens["ACCENT_ON"], 16))

    def _repolish(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


# =================================================================== log ====
class LogPanel(QFrame):
    """Structured log view."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("任务日志")
        title.setObjectName("logTitle")
        self.clear_button = QPushButton("清空")
        self.clear_button.setObjectName("ghostButton")
        self.copy_button = QPushButton("复制全部")
        self.copy_button.setObjectName("ghostButton")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.copy_button)
        header.addWidget(self.clear_button)
        layout.addLayout(header)

        self.view = QPlainTextEdit()
        self.view.setObjectName("logView")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(1200)
        self.view.setFont(fonts.make_font(size=9, mono=True))
        layout.addWidget(self.view, 1)

        self.clear_button.clicked.connect(self.view.clear)
        self.copy_button.clicked.connect(self.copy_all)

    def append_record(self, record: task_log.LogRecord) -> None:
        colors = theme.log_level_colors(theme.current_mode())
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colors.get(record.level, colors["info"])))
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(record.line() + "\n", fmt)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()

    def copy_all(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.view.toPlainText())


# ================================================================= preview ===
class PreviewPanel(QFrame):
    """Comparison stage with its own small toolbar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("预览对比")
        title.setObjectName("logTitle")
        self.zoom_label = MonoLabel("100%")
        self.zoom_label.setObjectName("cardHint")
        self.fit_button = QPushButton("适应")
        self.fit_button.setObjectName("ghostButton")
        self.zoom_out_button = IconButton("remove", "缩小", size=26)
        self.zoom_in_button = IconButton("add-file", "放大", size=26)
        self.hint_label = QLabel("拖动中缝对比")
        self.hint_label.setObjectName("previewCaption")
        header.addWidget(title)
        header.addWidget(self.hint_label)
        header.addStretch(1)
        header.addWidget(self.zoom_label)
        header.addWidget(self.zoom_out_button)
        header.addWidget(self.zoom_in_button)
        header.addWidget(self.fit_button)
        layout.addLayout(header)

        self.view = CompareView()
        layout.addWidget(self.view, 1)

        self.fit_button.clicked.connect(self.view.reset_view)
        self.zoom_in_button.clicked.connect(self.view.zoom_in)
        self.zoom_out_button.clicked.connect(self.view.zoom_out)
        self.view.zoomChanged.connect(self._on_zoom)

    def _on_zoom(self, _zoom: float) -> None:
        self.zoom_label.setText(f"{self.view.zoom_percent()}%")

    def show_comparison(
        self,
        before_path: Path | str,
        after_path: Path | str | None,
        before_size: int = 0,
        after_size: int = 0,
    ) -> None:
        before = load_pixmap(before_path)
        after = load_pixmap(after_path) if after_path else None
        caption_before = f"原始 · {human_size(before_size)}" if before_size else "原始"
        caption_after = f"压缩后 · {human_size(after_size)}" if after_size else "压缩后"
        if after is None:
            self.hint_label.setText("尚未压缩，显示原始图像")
        else:
            self.hint_label.setText("拖动中缝对比 · 滚轮缩放")
        self.view.set_images(before, after, caption_before, caption_after)
        self._on_zoom(self.view._zoom)

    def clear(self) -> None:
        self.view.clear()
        self.hint_label.setText("拖动中缝对比")


def make_scroll(inner: QWidget) -> QScrollArea:
    """Wrap a panel so it stays usable when the window is short."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(inner)
    inner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return area
