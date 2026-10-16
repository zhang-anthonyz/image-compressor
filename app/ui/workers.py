"""Batch execution: a thread pool over the queue.

Destination paths are resolved on the GUI thread *before* any worker starts, so
naming collisions and the batch-wide "already claimed" set are handled
deterministically instead of racing. Workers then only do CPU work and report
results back through queued signals.

Cancellation happens at file boundaries: one image cannot be interrupted
mid-encode (Pillow has no cancellation hook), but nothing new is started and
finished files are kept.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from ..core import naming, pipeline
from ..core.planner import CompressionPlan, resolve_workers
from ..core.task_log import LEVEL_ERROR, LEVEL_INFO, LEVEL_SUCCESS, LEVEL_WARNING


class BatchSignals(QObject):
    """Signals shared by every task in one batch."""

    file_started = Signal(int)
    file_finished = Signal(int, object)
    progress = Signal(int, int, int)  # processed, total, saved bytes
    finished = Signal(int, int, float)  # processed, failed, seconds
    log = Signal(str, str, str)  # level, message, source


class CompressTask(QRunnable):
    """Compresses exactly one file."""

    def __init__(
        self,
        row: int,
        source: Path,
        destination: Path,
        plan: CompressionPlan,
        signals: BatchSignals,
        cancelled: threading.Event,
    ) -> None:
        super().__init__()
        self._row = row
        self._source = source
        self._destination = destination
        self._plan = plan
        self._signals = signals
        self._cancelled = cancelled
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D102
        if self._cancelled.is_set():
            return
        self._signals.file_started.emit(self._row)
        result = pipeline.compress_file(self._source, self._plan, self._destination)
        self._signals.file_finished.emit(self._row, result)


class BatchRunner(QObject):
    """Owns the thread pool and turns queue items into compressed files."""

    #: (processed, total, saved_bytes)
    progress = Signal(int, int, int)
    #: (processed, failed, seconds)
    finished = Signal(int, int, float)

    def __init__(self, signals: BatchSignals, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._signals = signals
        self._pool = QThreadPool(self)
        self._cancelled = threading.Event()
        self._running = False
        self._processed = 0
        self._failed = 0
        self._saved = 0
        self._total = 0
        self._started_at = 0.0

        signals.file_finished.connect(self._on_file_finished)

    # ------------------------------------------------------------------ state
    @property
    def running(self) -> bool:
        return self._running

    @property
    def cancelled(self) -> bool:
        """Whether the current (or last) batch was stopped by the user."""
        return self._cancelled.is_set()

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancelled.set()
        self._signals.log.emit(LEVEL_WARNING, "正在停止：等待当前文件完成", "")

    # ------------------------------------------------------------------ start
    def start(
        self, items, plan: CompressionPlan, out_dir: Path | None
    ) -> tuple[int, list[tuple[int, pipeline.FileResult]]]:
        """Dispatch every enabled item.

        Returns ``(queued, rejected)``: rows that cannot be compressed at all are
        handed back to the caller instead of being signalled, because they are
        known before the batch starts and must not disturb its counters.
        """
        if self._running:
            return 0, []

        jobs: list[tuple[int, Path, Path]] = []
        taken: set[Path] = set()
        rejected: list[tuple[int, pipeline.FileResult]] = []

        for row, item in enumerate(items):
            if not item.enabled or item.status == pipeline.STATUS_SKIPPED:
                continue
            spec = None
            if item.probe is not None and item.probe.format_key:
                from ..core import formats

                spec = formats.BY_KEY.get(item.probe.format_key)
            target = plan.resolved_format(spec)
            if target is None and spec is None:
                rejected.append((row, pipeline.FileResult(
                    source=item.path, status=pipeline.STATUS_SKIPPED, message="无法识别的图片格式"
                )))
                continue
            if target is not None:
                issue = plan.issue_for(target)
                if issue is not None:
                    rejected.append((row, pipeline.FileResult(
                        source=item.path, status=pipeline.STATUS_SKIPPED, message=issue.message
                    )))
                    continue

            resolution = naming.resolve_output(
                item.path,
                plan,
                target,
                out_dir=None if plan.inplace else out_dir,
                taken=taken,
                width=item.probe.width if item.probe else 0,
                height=item.probe.height if item.probe else 0,
            )
            if resolution.path is None:
                rejected.append((row, pipeline.FileResult(
                    source=item.path,
                    status=pipeline.STATUS_SKIPPED,
                    message=resolution.skip_reason or "无法写入输出路径",
                )))
                continue
            taken.add(resolution.path)
            jobs.append((row, item.path, resolution.path))

        if not jobs:
            self._signals.log.emit(LEVEL_WARNING, "没有可压缩的文件", "")
            return 0, rejected

        self._cancelled.clear()
        self._running = True
        self._processed = 0
        self._failed = 0
        self._saved = 0
        self._total = len(jobs)
        self._started_at = time.perf_counter()

        workers = resolve_workers(plan.workers, len(jobs))
        self._pool.setMaxThreadCount(workers)
        self._signals.log.emit(
            LEVEL_INFO,
            f"开始压缩 {len(jobs)} 个文件 · {workers} 线程 · {plan.summary()}",
            "",
        )
        for row, source, destination in jobs:
            self._pool.start(
                CompressTask(row, source, destination, plan, self._signals, self._cancelled)
            )
        return len(jobs), rejected

    # --------------------------------------------------------------- plumbing
    def _on_file_finished(self, row: int, result: pipeline.FileResult) -> None:
        if not self._running:
            return
        self._processed += 1
        if result.status == pipeline.STATUS_FAILED:
            self._failed += 1
            self._signals.log.emit(LEVEL_ERROR, result.message, result.source.name)
        elif result.status == pipeline.STATUS_SKIPPED:
            self._signals.log.emit(LEVEL_WARNING, result.message, result.source.name)
        else:
            self._saved += result.saved_bytes
            note = result.note_text()
            self._signals.log.emit(
                LEVEL_SUCCESS,
                f"{-result.ratio * 100:.1f}% · {result.encoder}" + (f" · {note}" if note else ""),
                result.source.name,
            )
        self.progress.emit(self._processed, self._total, self._saved)

        if self._processed >= self._total:
            # Deferred by one event-loop turn: this runner connects to
            # file_finished before the window does, so finishing synchronously
            # here would emit `finished` while the model still lacks the last
            # file's result — and the summary would under-count by one.
            QTimer.singleShot(0, self._finish)

    def _finish(self) -> None:
        self._running = False
        elapsed = time.perf_counter() - self._started_at
        state = "已取消" if self._cancelled.is_set() else "全部完成"
        self._signals.log.emit(
            LEVEL_INFO,
            f"{state} · {self._processed - self._failed} 成功 · {self._failed} 失败 · {elapsed:.1f}s",
            "",
        )
        self.finished.emit(self._processed, self._failed, elapsed)

    def wait_for_done(self, timeout_ms: int = 120_000) -> bool:
        """Block until every task finished. Used by the headless self-check."""
        return self._pool.waitForDone(timeout_ms)
