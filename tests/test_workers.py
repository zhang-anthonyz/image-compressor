"""BatchRunner scheduling: cancellation must complete, never strand the runner.

The bug this covers: queueing every file up front meant cancel set a flag, the
not-yet-started tasks returned *without emitting*, and the runner waited
forever for file counts that would never arrive. With more files than worker
threads that was a silent hang.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from app.core import pipeline
from app.core.planner import CompressionPlan
from app.ui.workers import BatchRunner, BatchSignals


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _items(tmp_path: Path, count: int) -> list:
    items = []
    for index in range(count):
        path = tmp_path / f"image_{index}.png"
        path.write_bytes(b"not decoded by the fake")
        items.append(
            SimpleNamespace(
                path=path,
                enabled=True,
                status=pipeline.STATUS_PENDING,
                probe=SimpleNamespace(format_key="png", width=10, height=10),
            )
        )
    return items


def _result(source: Path) -> pipeline.FileResult:
    return pipeline.FileResult(
        source=source,
        status=pipeline.STATUS_DONE,
        original_size=1000,
        new_size=500,
        original_dimensions=(10, 10),
        new_dimensions=(10, 10),
        encoder="fake",
    )


def _wait(runner: BatchRunner, loop: QEventLoop, timeout_ms: int = 5000) -> None:
    runner.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    runner.wait_for_done(2000)


def test_cancel_stops_dispatch_and_finishes_after_inflight_files(tmp_path, monkeypatch, qt_app):
    release = threading.Event()

    def fake_compress(source, plan, destination):
        assert release.wait(5), "worker was never released"
        return _result(source)

    monkeypatch.setattr(pipeline, "compress_file", fake_compress)
    items = _items(tmp_path, 8)
    plan = CompressionPlan()
    plan.workers = 2
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    signals = BatchSignals()
    runner = BatchRunner(signals)
    loop = QEventLoop()
    queued, rejected = runner.start(items, plan, out_dir)
    assert (queued, rejected) == (8, [])
    assert runner.running and not runner.cancelling

    assert runner.cancel() is True
    assert runner.cancelling
    release.set()
    _wait(runner, loop)

    assert not runner.running
    assert runner.cancelled
    assert runner.processed == 2, "only the two in-flight files may finish"
    assert runner.total == 8
    assert runner.cancel() is False, "a second cancel must not report a new action"


def test_normal_run_processes_every_file(tmp_path, monkeypatch, qt_app):
    monkeypatch.setattr(
        pipeline,
        "compress_file",
        lambda source, plan, destination: _result(source),
    )
    items = _items(tmp_path, 5)
    plan = CompressionPlan()
    plan.workers = 3
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    runner = BatchRunner(BatchSignals())
    loop = QEventLoop()
    queued, _ = runner.start(items, plan, out_dir)
    assert queued == 5
    _wait(runner, loop)

    assert not runner.running
    assert not runner.cancelled
    assert runner.processed == 5
    assert runner.total == 5


def test_cancel_without_a_running_batch_is_a_noop(qt_app):
    runner = BatchRunner(BatchSignals())
    assert runner.cancel() is False
    assert runner.running is False
