"""Compression engine: format registry, planner, encoders, pipeline.

This package deliberately imports no Qt so the whole engine can be exercised
from pytest and from the ``--headless`` packaging self-check.
"""
from __future__ import annotations

# Optional decoders (HEIC) must be registered before anything checks what Pillow
# can open, so this happens on the first import of the engine.
from .imaging import enable_optional_codecs

enable_optional_codecs()
