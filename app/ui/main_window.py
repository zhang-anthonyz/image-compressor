"""The workspace window: queue on the left, settings and run controls on the right.

Layout intent (see docs/技术方案.md §7.3): a single instrument panel rather than
a pile of tabs, because compressing images is a watch-the-numbers activity —
the queue, the before/after seam and the running total all need to be visible
at once.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, APP_TAGLINE, APP_VERSION
from ..core import formats, pipeline, task_log
from ..core.encoders import registry
from ..core.planner import CompressionPlan
from ..core.settings_store import SettingsStore
from ..core.unit_report import human_size
from . import fonts, icons, theme, ui_logic
from .panels import LogPanel, PreviewPanel, SettingsPanel, TaskPanel, make_scroll
from .queue_model import (
    COL_DIMENSIONS,
    COL_ENABLED,
    COL_NAME,
    COL_ORIGINAL,
    COL_RESULT,
    COL_SAVINGS,
    QueueDelegate,
    QueueModel,
)
from .widgets import DropZone, IconButton, MicroLabel, MonoLabel, SegmentedControl, Toast
from .workers import BatchRunner, BatchSignals

TOAST_DIR_ERROR = "无法写入该输出目录，请检查权限"


class MainWindow(QMainWindow):
    """The whole application surface."""

    themeChanged = Signal(str)

    def __init__(self, store: SettingsStore) -> None:
        super().__init__()
        self._store = store
        self._plan: CompressionPlan = store.plan
        self._mode = "light"
        self._output_dir: Path | None = None

        self.setWindowTitle(f"{APP_NAME} · {APP_TAGLINE}")
        self.setMinimumSize(1080, 700)
        self.resize(store.window_width, store.window_height)
        self.setAcceptDrops(True)

        self.model = QueueModel(self)
        self.signals = BatchSignals(self)
        self.runner = BatchRunner(self.signals, self)
        self.log = task_log.TaskLog()

        self._build_ui()
        self._wire()
        self._install_shortcuts()

        self._plan = self.settings_panel.plan()
        self._sync_panels()
        self._refresh_theme_icons()
        self.log.info(f"{APP_NAME} {APP_VERSION} 就绪 · {registry.engine_badge()}")
        self.log_panel.append_record(self.log.records()[-1])

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_top_bar())

        content = QWidget()
        content.setObjectName("contentArea")
        body = QHBoxLayout(content)
        body.setContentsMargins(14, 12, 14, 10)
        body.setSpacing(12)
        body.addWidget(self._build_left_column(), 1)

        right = QWidget()
        right.setObjectName("pageBody")
        right.setFixedWidth(342)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        self.settings_panel = SettingsPanel(self._plan)
        right_layout.addWidget(make_scroll(self.settings_panel), 1)
        self.task_panel = TaskPanel()
        right_layout.addWidget(self.task_panel)
        body.addWidget(right)

        outer.addWidget(content, 1)
        outer.addWidget(self._build_status_bar())

        self.toast = Toast(self)

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(58)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 14, 0)
        layout.setSpacing(11)

        mark = QLabel("PP")
        mark.setObjectName("brandMark")
        mark.setFixedSize(30, 30)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mark)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        subtitle = QLabel(APP_TAGLINE)
        subtitle.setObjectName("brandSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        layout.addLayout(brand)

        layout.addSpacing(10)
        self.engine_chip = QLabel(registry.engine_badge())
        self.engine_chip.setObjectName("engineChip")
        self.engine_chip.setFont(fonts.make_font(size=9, mono=True))
        layout.addWidget(self.engine_chip)
        layout.addStretch(1)

        self.theme_button = IconButton("moon", "切换浅色 / 深色主题 (Ctrl+D)")
        self.info_button = IconButton("info", "关于与格式能力说明")
        layout.addWidget(self.theme_button)
        layout.addWidget(self.info_button)
        return bar

    def _build_left_column(self) -> QWidget:
        column = QWidget()
        column.setObjectName("pageBody")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ---- queue card
        queue_card = QFrame()
        queue_card.setObjectName("card")
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(14, 12, 14, 14)
        queue_layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(MicroLabel("QUEUE"))
        self.queue_title = QLabel("队列")
        self.queue_title.setObjectName("cardTitle")
        header.addWidget(self.queue_title)
        header.addStretch(1)
        self.queue_count = MonoLabel("0 个文件")
        self.queue_count.setObjectName("cardHint")
        header.addWidget(self.queue_count)
        queue_layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(7)
        self.add_files_button = QPushButton("添加文件")
        self.add_files_button.setIcon(icons.icon("add-file", theme.tokens_for("light")["TEXT_SECONDARY"], 17))
        self.add_files_button.setIconSize(QSize(15, 15))
        self.add_folder_button = QPushButton("添加文件夹")
        self.add_folder_button.setIcon(icons.icon("folder", theme.tokens_for("light")["TEXT_SECONDARY"], 17))
        self.add_folder_button.setIconSize(QSize(15, 15))
        self.remove_button = QPushButton("移除选中")
        self.remove_button.setIcon(icons.icon("remove", theme.tokens_for("light")["TEXT_SECONDARY"], 17))
        self.remove_button.setIconSize(QSize(15, 15))
        self.clear_button = QPushButton("清空")
        self.clear_button.setObjectName("ghostButton")
        for button in (self.add_files_button, self.add_folder_button, self.remove_button, self.clear_button):
            button.setMinimumHeight(29)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.select_all_button = QPushButton("全部参与")
        self.select_all_button.setObjectName("ghostButton")
        self.select_all_button.setMinimumHeight(29)
        toolbar.addWidget(self.select_all_button)
        queue_layout.addLayout(toolbar)

        self.table = QTableView()
        self.table.setObjectName("queueTable")
        self.table.setModel(self.model)
        self.table.setItemDelegate(QueueDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setMouseTracking(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        header_view = self.table.horizontalHeader()
        header_view.setHighlightSections(False)
        header_view.setFixedHeight(28)
        for section, width in (
            (COL_ENABLED, 34),
            (COL_DIMENSIONS, 158),
            (COL_ORIGINAL, 92),
            (COL_RESULT, 96),
            (COL_SAVINGS, 176),
        ):
            header_view.setSectionResizeMode(section, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(section, width)
        header_view.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)

        self.empty_state = self._build_empty_state()
        self.queue_stack = QStackedWidget()
        self.queue_stack.addWidget(self.empty_state)
        self.queue_stack.addWidget(self.table)
        self.queue_stack.setMinimumHeight(190)
        queue_layout.addWidget(self.queue_stack, 1)
        layout.addWidget(queue_card, 1)

        # ---- preview / log
        bottom_card = QFrame()
        bottom_card.setObjectName("card")
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(14, 11, 14, 13)
        bottom_layout.setSpacing(9)

        switch_row = QHBoxLayout()
        switch_row.setSpacing(8)
        self.bottom_switch = SegmentedControl([("preview", "预览对比"), ("log", "任务日志")])
        self.bottom_switch.set_value("preview" if not self._store.show_log else "log")
        switch_row.addWidget(self.bottom_switch)
        switch_row.addStretch(1)
        bottom_layout.addLayout(switch_row)

        self.preview_panel = PreviewPanel()
        self.log_panel = LogPanel()
        self.bottom_stack = QStackedWidget()
        self.bottom_stack.addWidget(self.preview_panel)
        self.bottom_stack.addWidget(self.log_panel)
        self.bottom_stack.setMinimumHeight(216)
        bottom_layout.addWidget(self.bottom_stack, 1)
        self._sync_bottom_stack()
        layout.addWidget(bottom_card)

        return column

    def _build_empty_state(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageBody")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        # Stretches above and below so the drop target sits optically centred in
        # the card instead of hugging the top edge.
        layout.addStretch(1)

        self.drop_zone = DropZone(
            "拖入图片或文件夹",
            f"支持 {'、'.join(self._supported_labels())}；HEIC 可读入并转为可写格式",
        )
        layout.addWidget(self.drop_zone)

        hint = QLabel(
            "无损模式建议选 WebP：实测图形类比 PNG 无损再小约 90%，且像素逐位一致。"
        )
        hint.setObjectName("cardHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(2)
        return page

    @staticmethod
    def _supported_labels() -> list[str]:
        seen: list[str] = []
        for key in formats.WRITABLE_KEYS:
            seen.append(formats.BY_KEY[key].label)
        return seen

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(28)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(14)

        self.status_text = QLabel("队列为空 · 拖入图片或点击「添加文件」开始")
        self.status_text.setObjectName("statusBarText")
        layout.addWidget(self.status_text)
        layout.addStretch(1)

        self.status_saved = QLabel("—")
        self.status_saved.setObjectName("statusBarAccent")
        self.status_saved.setFont(fonts.make_font(size=9, mono=True, weight=fonts.WEIGHT_BOLD))
        self.status_ratio = QLabel("—")
        self.status_ratio.setObjectName("statusBarValue")
        self.status_ratio.setFont(fonts.make_font(size=9, mono=True))
        self.status_engine = QLabel("")
        self.status_engine.setObjectName("statusBarText")
        self.status_engine.setFont(fonts.make_font(size=9, mono=True))
        for widget in (self.status_saved, self.status_ratio, self.status_engine):
            layout.addWidget(widget)
        return bar

    # ------------------------------------------------------------------- wire
    def _wire(self) -> None:
        self.add_files_button.clicked.connect(self._choose_files)
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_queue)
        self.select_all_button.clicked.connect(self._toggle_select_all)
        self.drop_zone.filesDropped.connect(self.add_paths)

        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.clicked.connect(self._on_table_clicked)

        self.bottom_switch.changed.connect(lambda _: self._sync_bottom_stack())

        self.settings_panel.changed.connect(self._on_settings_changed)
        self.settings_panel.open_dir_button.clicked.connect(self._open_output_dir)
        self.task_panel.startRequested.connect(self.start_batch)
        self.task_panel.cancelRequested.connect(self.runner.cancel)
        self.task_panel.openOutputRequested.connect(self._open_output_dir)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.info_button.clicked.connect(self._show_about)

        self.signals.file_started.connect(self.model.apply_running)
        self.signals.file_finished.connect(self._on_file_finished)
        self.signals.progress.connect(self._on_progress)
        self.signals.log.connect(self._on_log)
        self.runner.finished.connect(self._on_batch_finished)

        self.log.subscribe(self.log_panel.append_record)

    def _install_shortcuts(self) -> None:
        def shortcut(sequence: str, handler) -> None:
            QShortcut(QKeySequence(sequence), self, activated=handler)

        shortcut("Ctrl+O", self._choose_files)
        shortcut("Ctrl+Shift+O", self._choose_folder)
        shortcut("Ctrl+Return", self.start_batch)
        shortcut("Ctrl+Enter", self.start_batch)
        shortcut("Delete", self._remove_selected)
        shortcut("Esc", self.runner.cancel)
        shortcut("Ctrl+D", self.toggle_theme)
        shortcut("Ctrl+1", lambda: self.settings_panel.mode_control.set_value(ui_logic.MODE_LOSSLESS, notify=True))
        shortcut("Ctrl+2", lambda: self.settings_panel.mode_control.set_value(ui_logic.MODE_LOSSY, notify=True))
        shortcut("Ctrl++", self.preview_panel.view.zoom_in)
        shortcut("Ctrl+-", self.preview_panel.view.zoom_out)
        shortcut("Ctrl+0", self.preview_panel.view.reset_view)

    # ------------------------------------------------------------------ queue
    def _choose_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in formats.DIALOG_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", f"图片文件 ({patterns});;所有文件 (*)"
        )
        if paths:
            self.add_paths(paths)

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if directory:
            self.add_paths([directory])

    def add_paths(self, paths: list[str]) -> None:
        """Expand folders, filter by extension, probe, and append to the queue."""
        if self.runner.running:
            self._toast("压缩进行中，稍后再添加")
            return

        candidates: list[Path] = []
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and child.suffix.lower() in formats.DIALOG_EXTENSIONS:
                        candidates.append(child)
            elif path.is_file():
                candidates.append(path)

        if not candidates:
            self._toast("没有找到可识别的图片文件")
            return

        probes: dict[Path, pipeline.Probe] = {}
        for path in candidates:
            probes[path] = pipeline.probe(path)

        added = self.model.add_paths(candidates, probes)
        unsupported = sum(1 for probe in probes.values() if not probe.ok)
        animated = sum(1 for probe in probes.values() if probe.ok and probe.animated)

        if added:
            self._store.remember_inputs(candidates[:10])
            message = f"已添加 {added} 个文件"
            if unsupported:
                message += f" · {unsupported} 个无法识别"
            if animated:
                message += f" · {animated} 个动图已跳过"
            self._toast(message)
            self.log.info(message)
        else:
            self._toast("这些文件已在队列中")

        self._sync_panels()
        if self.table.currentIndex().row() < 0 and self.model.rowCount():
            self.table.selectRow(0)

    def _remove_selected(self) -> None:
        if self.runner.running:
            self._toast("压缩进行中，无法修改队列")
            return
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not rows:
            self._toast("先选中要移除的行")
            return
        self.model.remove_rows(rows)
        self._sync_panels()
        self._toast(f"已移除 {len(rows)} 行")

    def _clear_queue(self) -> None:
        if self.runner.running:
            self._toast("压缩进行中，无法清空队列")
            return
        if not self.model.rowCount():
            return
        self.model.clear()
        self.preview_panel.clear()
        self.task_panel.reset()
        self._sync_panels()

    def _toggle_select_all(self) -> None:
        items = self.model.items()
        if not items:
            return
        target = not all(item.enabled for item in items)
        self.model.set_enabled_all(target)
        self.select_all_button.setText("全部参与" if target else "全部跳过")
        self._sync_panels()

    def _on_table_clicked(self, index) -> None:
        if index.column() == COL_ENABLED:
            self.model.toggle_row(index.row())
            self._sync_panels()

    def _on_selection_changed(self, *args) -> None:
        item = self._selected_item()
        if item is None:
            self.settings_panel.set_context(None, None)
            return
        source_key = item.probe.format_key if item.probe else None
        size = item.probe.dimensions if item.probe else None
        self.settings_panel.set_context(source_key, size)
        self._refresh_preview(item)

    def _selected_item(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            return self.model.item(rows[0].row())
        if self.model.rowCount():
            return self.model.item(0)
        return None

    def _refresh_preview(self, item) -> None:
        after = None
        after_size = 0
        if item.result is not None and item.result.output is not None:
            after = item.result.output
            after_size = item.result.new_size
        before_size = item.original_size
        self.preview_panel.show_comparison(item.path, after, before_size, after_size)

    # ------------------------------------------------------------------- run
    def start_batch(self) -> None:
        if self.runner.running:
            return
        items = self.model.items()
        if not items:
            self._toast("先添加图片")
            return

        plan = self.settings_panel.plan()
        enabled = self.model.enabled_items()
        if not enabled:
            self._toast("所有文件都被排除，请勾选要压缩的文件")
            return

        if plan.inplace and not self._confirm_inplace():
            return

        out_dir = self._effective_out_dir(plan)
        if out_dir is not None:
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                self._toast(TOAST_DIR_ERROR)
                self.log.error(f"{TOAST_DIR_ERROR}: {out_dir}")
                return
            self._output_dir = out_dir
            self._store.last_output_dir = str(out_dir)
        else:
            self._output_dir = None

        self._plan = plan
        self.model.reset_results()
        queued, rejected = self.runner.start(items, plan, out_dir)
        for row, result in rejected:
            self.model.apply_result(row, result)

        if queued:
            self.task_panel.set_running(True)
            self.settings_panel.set_running(True)
            self.task_panel.set_status_text(f"0 / {queued} 个文件")
            self.task_panel.progress.setValue(0)
            self._sync_status()
        else:
            self._toast("没有可压缩的文件")
            self._sync_panels()

    def _effective_out_dir(self, plan: CompressionPlan) -> Path | None:
        if plan.inplace:
            return None
        if plan.out_dir:
            return Path(plan.out_dir)
        items = self.model.items()
        if items:
            return items[0].path.parent / "compressed"
        return None

    def _confirm_inplace(self) -> bool:
        answer = QMessageBox.warning(
            self,
            "确认覆盖源文件",
            "原地覆盖将直接改写源文件，无法通过本工具撤销。\n\n"
            "建议先在小批量上验证效果。确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self.log.warning("已开启原地覆盖模式")
        return True

    def _on_file_finished(self, row: int, result: pipeline.FileResult) -> None:
        self.model.apply_result(row, result)
        item = self.model.item(row)
        selected = self.table.selectionModel().selectedRows()
        if item is not None and selected and selected[0].row() == row:
            self._refresh_preview(item)

    def _on_progress(self, done: int, total: int, saved: int) -> None:
        self.task_panel.show_progress(done, total, saved)
        self.task_panel.set_status_text(f"{done} / {total} 个文件")
        self._sync_status()

    def _on_batch_finished(self, processed: int, failed: int, seconds: float) -> None:
        stats = self.model.stats()
        self.task_panel.set_running(False)
        self.settings_panel.set_running(False)
        duration_text = f"{seconds:.1f} s"
        if self.runner.cancelled:
            self.task_panel.show_cancelled(int(stats["processed"]), processed)
            self._toast(f"已取消 · 完成 {stats['processed']} 个")
        else:
            self.task_panel.show_result(
                int(stats["processed"]),
                int(stats["saved"]),
                float(stats["ratio"]),
                duration_text,
                failed,
            )
            self._toast(
                f"完成 {stats['processed']} 个文件 · 共省 {human_size(int(stats['saved']))}"
            )
        self._sync_panels()

    # ---------------------------------------------------------------- panels
    def _on_settings_changed(self) -> None:
        self._plan = self.settings_panel.plan()
        self._sync_status()
        if self.runner.running:
            self.task_panel.set_status_text("正在压缩 · 设置改动将在下一批生效")

    def _sync_panels(self) -> None:
        count = self.model.rowCount()
        self.queue_count.setText(f"{count} 个文件" if count else "暂无文件")
        self.queue_stack.setCurrentIndex(0 if count == 0 else 1)
        self.empty_state.setVisible(count == 0)
        self.table.setVisible(count > 0)
        stats = self.model.stats()
        ready = count > 0 and int(stats["enabled"]) > 0
        self.task_panel.set_ready(ready, count, self.runner.running)
        if ready and not self.runner.running:
            enabled = int(stats["enabled"])
            processed = int(stats["processed"])
            if processed and processed >= enabled:
                # A batch already ran; the summary block owns the outcome, so the
                # label only needs to say the queue is ready to run again.
                self.task_panel.set_status_text("本批已完成 · 调整设置后可再次压缩")
            else:
                self.task_panel.set_status_text(f"待压缩 {enabled} 个文件")
        self._sync_status()

    def _sync_status(self) -> None:
        stats = self.model.stats()
        self.status_text.setText(ui_logic.summary_line(stats, running=self.runner.running))
        saved = int(stats.get("saved", 0))
        self.status_saved.setText(human_size(saved) if saved else "—")
        ratio = float(stats.get("ratio", 0.0))
        self.status_ratio.setText(f"−{ratio * 100:.1f}%" if saved else "—")
        self.status_engine.setText(f"{stats.get('processed', 0)}/{stats.get('enabled', 0)}")

    def _sync_bottom_stack(self) -> None:
        index = 0 if self.bottom_switch.value() == "preview" else 1
        self.bottom_stack.setCurrentIndex(index)
        self._store.show_log = index == 1

    def _open_output_dir(self) -> None:
        directory = self._output_dir
        if directory is None and self._plan.out_dir:
            directory = Path(self._plan.out_dir)
        if directory is None:
            items = self.model.items()
            if items:
                directory = items[0].path.parent / "compressed"
        if directory is None:
            self._toast("还没有输出目录")
            return
        if not directory.exists():
            self._toast("输出目录尚未创建（压缩后自动创建）")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    # ----------------------------------------------------------------- theme
    def toggle_theme(self) -> None:
        self._mode = "dark" if self._mode == "light" else "light"
        from PySide6.QtWidgets import QApplication

        theme.apply_app_theme(QApplication.instance(), self._mode)
        self._store.theme_mode = self._mode
        self._refresh_theme_icons()
        self.drop_zone.refresh_theme()
        self.table.viewport().update()
        self.preview_panel.view.update()
        self.themeChanged.emit(self._mode)

    def set_theme(self, mode: str, resolved: str | None = None) -> None:
        from PySide6.QtWidgets import QApplication

        self._mode = theme.apply_app_theme(QApplication.instance(), mode, resolved)
        self._store.theme_mode = mode
        self._refresh_theme_icons()
        self.drop_zone.refresh_theme()

    def _refresh_theme_icons(self) -> None:
        tokens = theme.tokens_for(theme.current_mode())
        secondary = tokens["TEXT_SECONDARY"]
        self.add_files_button.setIcon(icons.icon("add-file", secondary, 17))
        self.add_folder_button.setIcon(icons.icon("folder", secondary, 17))
        self.remove_button.setIcon(icons.icon("remove", secondary, 17))
        self.theme_button._name = "sun" if theme.current_mode() == "dark" else "moon"
        self.theme_button.refresh_icon()
        self.info_button.refresh_icon()
        self.task_panel.refresh_icons()
        self.preview_panel.zoom_in_button.refresh_icon()
        self.preview_panel.zoom_out_button.refresh_icon()
        self.settings_panel.open_dir_button.refresh_icon()

    def _show_about(self) -> None:
        report = registry.engine_report()
        lines = [
            f"<b>{APP_NAME}</b> {APP_VERSION} · {APP_TAGLINE}",
            "",
            f"引擎：Pillow {report['pillow']}　oxipng {report['oxipng'] or '未内置'}",
            f"HEIC 读取：{'可用' if report['heif_available'] else '不可用'}",
            "",
            "<b>格式能力</b>",
        ]
        for spec in formats.writable_specs():
            caps = []
            caps.append("无损" if spec.can_lossless else "无无损")
            caps.append("有损" if spec.can_lossy else "无有损")
            lines.append(f"· {spec.label}：{' / '.join(caps)}")
        lines.extend(
            [
                "",
                "<b>实测参考</b>",
                "· WebP 无损：图形类比 PNG 无损再小约 90%（像素逐位一致）",
                "· oxipng：PNG 无损再省 11%（照片）～75%（图形）",
                "· JPEG 无损为「视觉无损」：沿用原量化表，实测 79.7 dB，非逐位相同",
            ]
        )
        box = QMessageBox(self)
        box.setWindowTitle("关于")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText("<br>".join(lines))
        box.exec()

    # ------------------------------------------------------------------ misc
    def _on_log(self, level: str, message: str, source: str) -> None:
        self.log.add(level, message, source)

    def _toast(self, text: str) -> None:
        self.toast.show_message(text)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.toast.refresh_geometry()

    # drag & drop anywhere on the window
    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            self.drop_zone.set_state("active")
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):  # noqa: N802
        self.drop_zone.set_state("idle")

    def dropEvent(self, event):  # noqa: N802
        self.drop_zone.set_state("idle")
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_paths(paths)
        event.acceptProposedAction()

    def closeEvent(self, event):  # noqa: N802
        if self.runner.running:
            answer = QMessageBox.question(
                self,
                "仍在压缩",
                "还有文件正在压缩，确定退出吗？未完成的文件不会被写入。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.cancel()
        self._store.plan = self.settings_panel.plan()
        self._store.window_width = self.width()
        self._store.window_height = self.height()
        self._store.save()
        super().closeEvent(event)
