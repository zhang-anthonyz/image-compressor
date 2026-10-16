"""oxipng wrapper: the PNG lossless upgrade path.

oxipng (MIT) re-compresses an existing PNG without touching a single pixel —
it re-runs the filter heuristic and deflate with a better strategy. Measured on
this machine: 11.2% smaller on a photo fixture, 75.5% on flat graphics.

Design rules:

* The binary is optional. If ``vendor/oxipng.exe`` is missing, everything still
  works and the pipeline keeps Pillow's output.
* Any failure (timeout, non-zero exit, unreadable output) degrades to the
  Pillow result — a compression tool must never fail a file because an
  optional optimiser misbehaved.
* ``--strip none``: the PNG handed to oxipng was just written by Pillow and
  contains exactly the metadata we decided to keep, so oxipng must not make
  metadata decisions of its own.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..paths import vendor_binary
from ..planner import Effort

#: Per-effort optimisation level. Level 6 is exhaustive; the measured gain over
#: level 4 is under 0.1% while --zopfli costs ~10x wall time for ~0.05%, so
#: neither "max" nor any zopfli pass is worth it.
_LEVELS = {Effort.FAST: "2", Effort.BALANCED: "4", Effort.MAX: "6"}


class OxipngEncoder:
    """Runs the bundled oxipng binary over PNG bytes."""

    name = "oxipng"

    def __init__(self, binary: Path | None = None) -> None:
        self._binary = binary

    @property
    def binary(self) -> Path:
        return self._binary if self._binary is not None else vendor_binary("oxipng.exe")

    def available(self) -> bool:
        try:
            return self.binary.is_file()
        except OSError:
            return False

    def version(self) -> str:
        """Reported version, or an empty string when unavailable."""
        if not self.available():
            return ""
        try:
            done = subprocess.run(
                [str(self.binary), "--version"],
                capture_output=True, text=True, timeout=10,
                creationflags=_no_window(),
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        text = (done.stdout or done.stderr or "").strip().splitlines()
        return text[0].strip() if text else ""

    def _timeout_for(self, size: int) -> float:
        """Scale the timeout with payload size (level 6 on 100 MP is not fast)."""
        return min(600.0, 120.0 + (size / 1_000_000.0) * 25.0)

    def optimize(self, data: bytes, effort: Effort) -> bytes | None:
        """Return optimised PNG bytes, or ``None`` to keep the input."""
        if not self.available() or not data:
            return None
        try:
            with tempfile.TemporaryDirectory(prefix="pixelpress-oxipng-") as tmp:
                src = Path(tmp) / "in.png"
                dst = Path(tmp) / "out.png"
                src.write_bytes(data)
                done = subprocess.run(
                    [
                        str(self.binary),
                        "--opt", _LEVELS[effort],
                        "--strip", "none",
                        str(src),
                        "--out", str(dst),
                    ],
                    capture_output=True, text=True,
                    timeout=self._timeout_for(len(data)),
                    creationflags=_no_window(),
                )
                if done.returncode != 0 or not dst.is_file():
                    return None
                optimised = dst.read_bytes()
        except (OSError, subprocess.SubprocessError):
            return None
        # Sanity: never hand back something that is not a PNG, or is bigger.
        if not optimised.startswith(b"\x89PNG\r\n\x1a\n") or len(optimised) >= len(data):
            return None
        return optimised


def _no_window() -> int:
    """Keep the console window from flashing when spawning the helper."""
    import sys

    if sys.platform != "win32":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
