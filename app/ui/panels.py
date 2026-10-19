"""The workspace panels.

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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core import task_log
from ..core.planner import CompressionPlan, Effort, MetadataPolicy, NamingPolicy, clamp_quality, clamp_scale
from ..core.unit_report import human_size
from . import fonts, icons, theme, ui_logic
from .preview import CompareView, load_pixmap
from .widgets import (
    ChevronComboBox,
    IconButton,
    MonoLabel,
    PlusMinusSpinBox,
    PressSlider,
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
        self.quality_slider = PressSlider()
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(plan.quality)
        self.quality_slider.set_tick_values([25, 50, 75])
        self.quality_slider.set_default_value(75)
        self.quality_slider.setMinimumWidth(110)
        self.quality_spin = PlusMinusSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(plan.quality)
        self.quality_spin.setFixedWidth(76)
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
        form.addRow(self.quality_hint)

        form.addRow(divider())

        # ---- scale
        scale_row = QHBoxLayout()
        scale_row.setSpacing(9)
        self.scale_slider = PressSlider()
        self.scale_slider.setRange(5, 100)
        self.scale_slider.setValue(int(plan.scale_percent))
        self.scale_slider.set_tick_values([25, 50, 75, 100])
        self.scale_slider.set_default_value(100)
        self.scale_slider.set_suffix(" %")
        self.scale_spin = PlusMinusSpinBox()
        self.scale_spin.setRange(5, 100)
        self.scale_spin.setValue(int(plan.scale_percent))
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setFixedWidth(82)
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
        form.addRow(self.scale_readout)

        form.addRow(divider())

        # ---- format / metadata
        self.format_combo = ChevronComboBox()
        self.format_combo.setSizeAdjustPolicy(ChevronComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.format_combo.setMinimumContentsLength(8)
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
        form.addRow(self.format_note)

        self.note_label = QLabel("")
        self.note_label.setObjectName("noteLabel")
        self.note_label.setWordWrap(True)
        self.note_label.hide()
        form.addRow(self.note_label)

        form.addRow(divider())

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
        self.naming_combo.setFixedWidth(118)
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
        form.addRow(self.naming_preview)

        form.addRow(divider())

        # ---- effort
        self.effort_control = SegmentedControl(ui_logic.effort_options())
        self.effort_control.set_value(plan.effort.value)
        form.addRow(_form_label("力度", "快速更省时间，极致更省体积"), self.effort_control)

        workers_row = QHBoxLayout()
        workers_row.setSpacing(6)
        self.workers_spin = PlusMinusSpinBox()
        self.workers_spin.setRange(0, 32)
        self.workers_spin.setValue(plan.workers)
        self.workers_spin.setFixedWidth(76)
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
    """Run controls, live progress and the post-batch summary.

    The panel is a small state machine — empty / ready / running / cancelling /
    done / cancelled. The state badge and the button set are derived from it, so
    "start" and "cancel" can never both look like the primary action.
    """

    startRequested = Signal()
    cancelRequested = Signal()
    openOutputRequested = Signal()

    STATE_EMPTY = "empty"
    STATE_READY = "ready"
    STATE_RUNNING = "running"
    STATE_CANCELLING = "cancelling"
    STATE_DONE = "done"
    STATE_CANCELLED = "cancelled"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = self.STATE_EMPTY
        self._total = 0

        self.state_badge = QLabel("待开始")
        self.state_badge.setObjectName("stateBadge")
        self.state_badge.setProperty("state", "idle")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card, body = make_card("任务", eyebrow="RUN", header_right=self.state_badge, parent=self)
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
        self.cancel_button = QPushButton("取消压缩")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setMinimumWidth(96)
        self.cancel_button.setIcon(icons.icon("stop", theme.tokens_for("light")["DANGER"], 16))
        self.cancel_button.setIconSize(QSize(14, 14))
        self.cancel_button.hide()
        self.open_button = QPushButton("打开输出目录")
        self.open_button.setObjectName("softButton")
        self.open_button.setEnabled(False)
        self.start_button = QPushButton("开始压缩")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setIcon(icons.icon("play", theme.tokens_for("light")["ACCENT_ON"], 16))
        self.start_button.setIconSize(QSize(15, 15))
        self.start_button.setMinimumWidth(112)
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

    # ------------------------------------------------------------------ state
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str, label: str, badge_state: str) -> None:
        self._state = state
        self.state_badge.setText(label)
        self.state_badge.setProperty("state", badge_state)
        self._repolish(self.state_badge)

    def _set_progress_state(self, state: str) -> None:
        self.progress.setProperty("state", state)
        self._repolish(self.progress)

    def _terminal(self) -> bool:
        return self._state in (self.STATE_DONE, self.STATE_CANCELLED)

    def set_ready(self, ready: bool, count: int, enabled: int, running: bool) -> None:
        """Reflect queue readiness; never clobber a finished batch's outcome."""
        if running:
            return
        self.cancel_button.hide()
        if self._terminal():
            self.start_button.setText("再次压缩")
            self.start_button.setEnabled(ready)
            return
        self.start_button.setText("开始压缩")
        self.start_button.setEnabled(ready)
        if count == 0:
            self._set_state(self.STATE_EMPTY, "队列为空", "idle")
            self.summary.show_idle()
            self.progress.setValue(0)
            self._set_progress_state("idle")
            self.status_label.setText("队列为空 · 添加图片后即可开始")
            self.open_button.setEnabled(False)
        elif not ready:
            self._set_state(self.STATE_EMPTY, "无可压缩项", "idle")
            self.summary.show_idle()
            self.status_label.setText("所有文件都被排除 · 勾选后即可开始")
            self.open_button.setEnabled(False)
        else:
            self._set_state(self.STATE_READY, "待开始", "idle")
            self.summary.show_ready(enabled)
            self.progress.setValue(0)
            self._set_progress_state("idle")
            self.status_label.setText(f"待压缩 {enabled} 个文件")
            self.open_button.setEnabled(False)

    def begin_run(self, total: int) -> None:
        self._total = max(1, total)
        self._set_state(self.STATE_RUNNING, "运行中", "running")
        self._set_progress_state("running")
        self.progress.setValue(0)
        self.summary.show_progress(0, self._total, 0)
        self.status_label.setText(f"正在压缩 · 0 / {self._total}")
        self.start_button.setText("压缩中…")
        self.start_button.setEnabled(False)
        self.cancel_button.setText("取消压缩")
        self.cancel_button.setIcon(
            icons.icon("stop", theme.tokens_for(theme.current_mode())["DANGER"], 16)
        )
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.open_button.setEnabled(False)

    def show_cancelling(self, done: int) -> None:
        """Immediate feedback for the cancel click; the batch still has to
        finish the files already inside an encoder."""
        self._set_state(self.STATE_CANCELLING, "正在取消", "cancelling")
        self._set_progress_state("cancelling")
        self.cancel_button.setText("正在取消…")
        self.cancel_button.setEnabled(False)
        self.summary.show_cancelling(done, self._total)
        self.status_label.setText("正在取消 · 等待当前文件完成")

    def set_status_text(self, text: str) -> None:
        self.status_label.setText(text)

    def show_progress(self, done: int, total: int, saved: int) -> None:
        self._total = max(1, total)
        self.progress.setValue(int(1000 * done / total) if total else 0)
        self.summary.show_progress(done, self._total, saved)
        if self._state == self.STATE_CANCELLING:
            self.status_label.setText(f"已处理 {done} / {self._total} · 正在取消")
        elif self._state == self.STATE_RUNNING:
            self.status_label.setText(f"正在压缩 · {done} / {self._total}")

    def show_result(self, total: int, saved: int, ratio: float, duration: str, failures: int) -> None:
        self._set_state(self.STATE_DONE, "已完成", "done")
        self.progress.setValue(1000)
        self._set_progress_state("failed" if failures else "done")
        self.summary.show_result(total, saved, ratio, duration, failures)
        self.status_label.setText(
            "本批完成 · 调整设置后可再次压缩" + (f" · {failures} 个失败" if failures else "")
        )
        self.start_button.setText("再次压缩")
        self.start_button.setEnabled(True)
        self.cancel_button.hide()
        self.open_button.setEnabled(True)

    def show_cancelled(self, done: int, total: int) -> None:
        self._total = max(1, total)
        self._set_state(self.STATE_CANCELLED, "已取消", "cancelled")
        self.progress.setValue(int(1000 * done / self._total) if self._total else 0)
        self._set_progress_state("cancelled")
        self.summary.show_cancelled(done, self._total)
        self.status_label.setText(
            f"已取消 · 完成 {done} / {self._total} 个（已完成的结果已写入磁盘）"
        )
        self.start_button.setText("再次压缩")
        self.start_button.setEnabled(True)
        self.cancel_button.hide()
        self.open_button.setEnabled(done > 0)

    def reset(self) -> None:
        self._set_state(self.STATE_EMPTY, "队列为空", "idle")
        self.progress.setValue(0)
        self._set_progress_state("idle")
        self.summary.show_idle()
        self.status_label.setText("队列为空 · 添加图片后即可开始")
        self.start_button.setText("开始压缩")
        self.start_button.setEnabled(False)
        self.cancel_button.hide()
        self.open_button.setEnabled(False)

    def refresh_icons(self) -> None:
        tokens = theme.tokens_for(theme.current_mode())
        self.start_button.setIcon(icons.icon("play", tokens["ACCENT_ON"], 16))
        self.cancel_button.setIcon(icons.icon("stop", tokens["DANGER"], 16))

    def _repolish(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


# =================================================================== log ====
class LogPanel(QWidget):
    """Structured log view. Its toolbar lives in the bottom card header."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view = QPlainTextEdit()
        self.view.setObjectName("logView")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(1200)
        self.view.setFont(fonts.make_font(size=9, mono=True))
        layout.addWidget(self.view, 1)

    def append_record(self, record: task_log.LogRecord) -> None:
        colors = theme.log_level_colors(theme.current_mode())
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colors.get(record.level, colors["info"])))
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(record.line() + "\n", fmt)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()

    def clear(self) -> None:
        self.view.clear()

    def copy_all(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.view.toPlainText())


# ================================================================= preview ===
class PreviewPanel(QWidget):
    """The comparison stage. Its toolbar lives in the bottom card header."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.view = CompareView()
        layout.addWidget(self.view, 1)

    def show_comparison(
        self,
        before_path: Path | str,
        after_path: Path | str | None,
        before_size: int = 0,
        after_size: int = 0,
    ) -> str:
        before = load_pixmap(before_path)
        after = load_pixmap(after_path) if after_path else None
        if before is None:
            self.view.set_images(None, None, "", "")
            return "无法读取预览图"
        caption_before = f"原始 · {human_size(before_size)}" if before_size else "原始"
        caption_after = f"压缩后 · {human_size(after_size)}" if after_size else "压缩后"
        if after is None:
            hint = "尚未压缩 · 显示原图 · Ctrl+滚轮缩放"
            self.view.set_images(before, None, caption_before, "")
        else:
            hint = "拖动中缝对比 · Ctrl+滚轮缩放 · 滚轮上下滚动"
            self.view.set_images(before, after, caption_before, caption_after)
        return hint

    def clear(self) -> str:
        self.view.clear()
        return "选择队列中的文件以查看对比"


def make_scroll(inner: QWidget) -> QScrollArea:
    """Wrap a panel so it stays usable when the window is short."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(inner)
    inner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return area
