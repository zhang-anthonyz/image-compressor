"""Encoder protocol shared by the Pillow and oxipng backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from PIL import Image

from ..formats import FormatSpec
from ..planner import Effort, Mode


@dataclass
class EncodeRequest:
    """Everything an encoder may need, gathered once by the pipeline."""

    image: Image.Image
    target: FormatSpec
    mode: Mode
    quality: int
    effort: Effort
    #: Output of ``plan.pillow_params`` — the encoder translates this into
    #: actual Pillow keyword arguments.
    params: dict
    source_pillow_format: str | None = None
    icc_profile: bytes | None = None
    exif_bytes: bytes | None = None
    background: tuple[int, int, int] = (255, 255, 255)
    #: Filled when the pipeline had to alter the pixels (alpha flattened,
    #: 16-bit reduced, palette-quantized). Surfaced to the user per file.
    notes: list[str] = field(default_factory=list)


@dataclass
class EncodeResult:
    """Encoded bytes plus provenance for the per-file report."""

    data: bytes
    encoder: str
    notes: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.data)

    def note_text(self) -> str:
        return "；".join(self.notes)


class Encoder(Protocol):
    """Structural type for anything that can turn an EncodeRequest into bytes."""

    name: str

    def available(self) -> bool: ...

    def encode(self, request: EncodeRequest) -> EncodeResult: ...
