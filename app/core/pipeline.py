"""Single-file pipeline: decode → orient → scale → encode → verify → write.

Everything that can go wrong with a real-world image is handled here rather
than in the UI: decompression bombs, animated containers, corrupt files,
alpha-less targets, and the case where "compression" would make a file bigger.
"""
from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from . import formats
from .encoders.base import EncodeRequest
from .encoders.registry import encode
from .formats import FormatSpec
from .planner import CompressionPlan, MetadataPolicy, Mode
from .unit_report import scale_target

# Pillow's own bomb guard is disabled because we enforce a clearer, explicit
# limit below and want to fail with a readable Chinese message, not a warning.
Image.MAX_IMAGE_PIXELS = None

#: 500 MP. Above this we refuse rather than risk exhausting memory: a 500 MP
#: RGBA image already needs ~2 GB to decode.
MAX_PIXELS = 500_000_000

#: 274 = EXIF Orientation.
_ORIENTATION_TAG = 274

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_UNCHANGED = "unchanged"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"


@dataclass
class Probe:
    """Cheap header-only read, used when files join the queue."""

    path: Path
    ok: bool
    format_key: str = ""
    format_label: str = ""
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    animated: bool = False
    has_alpha: bool = False
    error: str = ""

    @property
    def dimensions(self) -> tuple[int, int]:
        return self.width, self.height


@dataclass
class FileResult:
    """Outcome for one file, for the queue table and the summary strip."""

    source: Path
    status: str
    output: Path | None = None
    original_size: int = 0
    new_size: int = 0
    original_dimensions: tuple[int, int] = (0, 0)
    new_dimensions: tuple[int, int] = (0, 0)
    encoder: str = ""
    message: str = ""
    notes: list[str] = field(default_factory=list)
    duration: float = 0.0

    @property
    def saved_bytes(self) -> int:
        if self.status in (STATUS_DONE, STATUS_UNCHANGED) and self.new_size:
            return max(0, self.original_size - self.new_size)
        return 0

    @property
    def ratio(self) -> float:
        if not self.original_size or not self.new_size:
            return 0.0
        return max(0.0, min(1.0, 1 - self.new_size / self.original_size))

    @property
    def succeeded(self) -> bool:
        return self.status in (STATUS_DONE, STATUS_UNCHANGED)

    def note_text(self) -> str:
        return "；".join(self.notes)


def _has_alpha_mode(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA", "RGBa", "La"):
        return True
    return image.mode == "P" and "transparency" in image.info


def probe(path: str | Path) -> Probe:
    """Read only the header: format, dimensions, frame count, alpha presence."""
    file_path = Path(path)
    try:
        size_bytes = file_path.stat().st_size
    except OSError as exc:
        return Probe(path=file_path, ok=False, error=f"无法读取文件：{exc.strerror or exc}")

    try:
        with Image.open(file_path) as image:
            spec = formats.spec_for_pillow_name(image.format) or formats.detect(file_path)
            animated = getattr(image, "n_frames", 1) > 1
            has_alpha = image.mode in ("RGBA", "LA", "PA") or (
                image.mode == "P" and "transparency" in image.info
            )
            return Probe(
                path=file_path,
                ok=True,
                format_key=spec.key if spec else "",
                format_label=spec.label if spec else (image.format or "未知"),
                width=image.width,
                height=image.height,
                size_bytes=size_bytes,
                animated=animated,
                has_alpha=has_alpha,
            )
    except Exception as exc:  # Pillow raises a wide range on damaged files
        return Probe(
            path=file_path,
            ok=False,
            size_bytes=size_bytes,
            error=f"无法识别图片：{type(exc).__name__}",
        )


def _exif_for_policy(image: Image.Image, policy: MetadataPolicy) -> bytes | None:
    """EXIF payload to write, honouring the metadata policy.

    Orientation is always removed because the pipeline bakes it into pixels —
    leaving it behind is exactly what makes viewers double-rotate an image.

    The source's ``Exif`` object is *never* mutated: it belongs to the image we
    are about to read the orientation from, and deleting the tag in place would
    silently disable the rotation we are about to perform.
    """
    if policy in (MetadataPolicy.SLIM, MetadataPolicy.STRIP):
        return None

    fresh = Image.Exif()
    try:
        raw = image.info.get("exif")
        if raw:
            fresh.load(raw)
        else:
            source = image.getexif()
            if not source:
                return None
            fresh.load(source.tobytes())
    except Exception:
        return None

    fresh.pop(_ORIENTATION_TAG, None)
    try:
        payload = fresh.tobytes()
    except Exception:
        return None
    return payload or None


def _sanitize_info(image: Image.Image, policy: MetadataPolicy) -> None:
    """Drop metadata that Pillow would otherwise write back from ``im.info``.

    Pillow's encoders fall back to ``im.info["icc_profile"]`` / ``im.info["exif"]``
    when no explicit keyword is given, so stripping has to happen on the image
    itself — passing nothing is not enough.
    """
    for key in ("exif", "xmp", "XML:com.adobe.xmp", "comment"):
        image.info.pop(key, None)
    if policy is MetadataPolicy.STRIP:
        image.info.pop("icc_profile", None)


def _icc_for_policy(image: Image.Image, policy: MetadataPolicy) -> bytes | None:
    if policy is MetadataPolicy.STRIP:
        return None
    icc = image.info.get("icc_profile")
    return bytes(icc) if icc else None


def _write_atomic(path: Path, data: bytes) -> None:
    """Write via a sibling temp file so a crash never leaves a half file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.pixelpress-part")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def compress_file(
    source: str | Path,
    plan: CompressionPlan,
    destination: Path | None = None,
    *,
    source_spec: FormatSpec | None = None,
) -> FileResult:
    """Compress one file. Never raises for per-file problems."""
    started = time.perf_counter()
    file_path = Path(source)
    result = FileResult(source=file_path, status=STATUS_FAILED)

    try:
        original_bytes = file_path.read_bytes()
    except OSError as exc:
        result.message = f"读取失败：{exc.strerror or exc}"
        return result

    result.original_size = len(original_bytes)

    try:
        with Image.open(io.BytesIO(original_bytes)) as opened:
            source_pillow_format = (opened.format or "").upper()
            spec = source_spec or formats.spec_for_pillow_name(source_pillow_format) or formats.detect(file_path)
            target = plan.resolved_format(spec)
            if target is None:
                result.status = STATUS_SKIPPED
                result.message = "无法识别的图片格式"
                return result
            if plan.target_format is None and spec is not None and not spec.can_write:
                # Decode-only source (HEIC …): pick the container from what the
                # picture actually contains, so alpha is never thrown away.
                target = formats.BY_KEY["png" if _has_alpha_mode(opened) else "jpeg"]

            result.original_dimensions = (opened.width, opened.height)

            if getattr(opened, "n_frames", 1) > 1:
                result.status = STATUS_SKIPPED
                result.message = "动图暂不支持（GIF/WebP 多帧）"
                return result

            pixels = opened.width * opened.height
            if pixels > MAX_PIXELS:
                result.status = STATUS_SKIPPED
                result.message = f"图片过大（{pixels / 1e6:.0f} MP，上限 {MAX_PIXELS / 1e6:.0f} MP）"
                return result

            issue = plan.issue_for(target)
            if issue is not None:
                result.status = STATUS_SKIPPED
                result.message = issue.message
                return result

            icc = _icc_for_policy(opened, plan.metadata)
            exif = _exif_for_policy(opened, plan.metadata)

            # Bake the EXIF orientation into pixels first, so scaling and any
            # later metadata stripping keep the picture the right way up.
            image = ImageOps.exif_transpose(opened)
            if image is None:
                image = opened.copy()
            _sanitize_info(image, plan.metadata)

            if plan.scale_percent < 100.0:
                wanted = scale_target(image.size, plan.scale_percent)
                if wanted != image.size:
                    image = image.resize(wanted, Image.Resampling.LANCZOS)

            result.new_dimensions = image.size

            params = plan.pillow_params(target, source_pillow_format)
            request = EncodeRequest(
                image=image,
                target=target,
                mode=plan.effective_mode(target),
                quality=plan.quality,
                effort=plan.effort,
                params=params,
                source_pillow_format=source_pillow_format,
                icc_profile=icc,
                exif_bytes=exif,
                background=plan.background,
            )
            encoded = encode(request)

            payload = encoded.data
            status = STATUS_DONE
            notes = list(encoded.notes)
            message = ""

            # "No gain, keep the original" only makes sense when the container
            # is unchanged. If the user asked for a format conversion, honour
            # the conversion and simply report the size change — writing PNG
            # bytes into a .jpg path would be a lie.
            same_container = spec is not None and spec.key == target.key
            if plan.keep_smaller and same_container and len(payload) >= len(original_bytes):
                payload = original_bytes
                status = STATUS_UNCHANGED
                message = "压缩收益为负，已保留原文件"
                notes.append(
                    f"编码结果 {len(encoded.data) / 1024:.0f} KB ≥ 原始 {len(original_bytes) / 1024:.0f} KB"
                )

            result.new_size = len(payload)
            result.encoder = encoded.encoder
            result.notes = notes
            result.message = message or (notes[0] if notes else "")

            if destination is None:
                result.status = STATUS_SKIPPED
                result.message = result.message or "未指定输出路径"
                return result

            _write_atomic(Path(destination), payload)
            result.output = Path(destination)
            result.status = status
    except Exception as exc:  # one bad file must never take the batch down
        result.status = STATUS_FAILED
        result.message = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        result.duration = time.perf_counter() - started

    if result.status is STATUS_DONE:
        _verify(result)
    return result


def _verify(result: FileResult) -> None:
    """Re-open the written file and confirm the pixels are what we promised."""
    if result.output is None:
        return
    try:
        with Image.open(result.output) as check:
            check.load()
            if result.new_dimensions and (check.width, check.height) != result.new_dimensions:
                result.notes.append("输出尺寸校验不一致")
    except Exception as exc:
        result.status = STATUS_FAILED
        result.message = f"输出校验失败：{type(exc).__name__}"


def estimate_plan_note(target: FormatSpec, plan: CompressionPlan) -> str:
    """Short, honest description of what this plan will do (UI hint text)."""
    if plan.effective_mode(target) is Mode.LOSSLESS:
        return target.lossless_note or "无损重压缩，像素与压缩前一致"
    return f"有损压缩，质量 {plan.quality}（{plan.quality and _quality_band(plan.quality)}）"


def _quality_band(quality: int) -> str:
    from .planner import quality_label

    return quality_label(quality)
