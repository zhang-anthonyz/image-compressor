"""Pillow-backed encoder: the base path for every format.

Responsibilities, in order:

1. normalize the image mode for the *target* container,
2. composite transparency onto a chosen background when the container cannot
   hold an alpha channel (never silently drop it — that is how transparent
   areas become black),
3. quantize to a palette for lossy PNG / GIF,
4. attach ICC and EXIF only where the container supports them,
5. hand a fully-formed keyword set to ``Image.save``.

Every pixel-level deviation from the source is recorded as a note so the UI can
tell the user exactly what happened to a file.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps

from ..planner import Mode
from .base import EncodeRequest, EncodeResult

#: Image modes that carry more precision than 8 bits per channel.
_HIGH_DEPTH_MODES = ("I", "I;16", "I;16B", "I;16L", "I;16N", "F")
_ALPHA_MODES = ("RGBA", "LA", "PA", "RGBa", "La")


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in _ALPHA_MODES:
        return True
    return image.mode == "P" and "transparency" in image.info


def _flatten(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    """Composite an alpha image onto a solid background."""
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, background)
    canvas.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
    return canvas


def _reduce_depth(image: Image.Image, notes: list[str]) -> Image.Image:
    """16/32-bit input reduced to 8-bit for containers that cannot hold it."""
    mode = image.mode
    if mode in ("I;16", "I;16B", "I;16L", "I;16N"):
        reduced = image.point(lambda value: value * (1.0 / 256.0)).convert("L")
    else:  # mode "I" or "F": 32-bit integer / float, clamp into 8-bit
        reduced = image.point(lambda value: max(0, min(255, int(value)))).convert("L")
    notes.append("16 位灰度已降为 8 位")
    return reduced


def _normalize(image: Image.Image, request: EncodeRequest) -> Image.Image:
    """Return an image whose mode the target encoder can actually write."""
    target = request.target
    notes = request.notes
    img = image

    if img.mode in _HIGH_DEPTH_MODES:
        # 16-bit survives only in containers we are allowed to keep it in.
        keeps_depth = target.key in ("png", "tiff")
        if not keeps_depth:
            img = _reduce_depth(img, notes)

    if img.mode == "P" and "transparency" in img.info:
        img = img.convert("RGBA")

    if img.mode == "CMYK":
        # Keep CMYK only for JPEG-with-profile (correct colour); anything else
        # would risk the classic inverted-CMYK trap in viewers.
        if target.key == "jpeg" and request.icc_profile and request.source_pillow_format in ("JPEG", "MPO"):
            return img
        img = img.convert("RGB")
        notes.append("CMYK 已转 RGB")

    if not target.supports_alpha and _has_alpha(img):
        img = _flatten(img, request.background)
        notes.append(f"透明区域已铺底 RGB{request.background}")

    if img.mode in ("LA", "PA"):
        img = img.convert("RGBA")

    if target.key in ("jpeg", "bmp", "ppm") and img.mode not in ("RGB", "L", "CMYK"):
        img = img.convert("RGB")

    if target.key == "jpeg" and img.mode == "CMYK":
        pass  # CMYK JPEG is legal and handled above
    return img


def _quantize_for_png(img: Image.Image, colors: int, notes: list[str]) -> Image.Image | None:
    """Palette-reduce for lossy PNG. ``None`` means "not possible, stay lossless"."""
    try:
        if img.mode in ("RGB", "L", "1", "P"):
            quantized = img.quantize(
                colors=colors,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            notes.append(f"颜色量化至 {colors} 色")
            return quantized
        if img.mode == "RGBA":
            # FASTOCTREE spends the palette on the alpha channel: a smooth RGBA
            # ramp requested at 256 colours came back with only 60, which is the
            # severe banding/cast users saw on transparent PNGs. Quantize the
            # colour channels with the full palette, then put the original alpha
            # back at 8-bit precision. The file is RGBA rather than palette-PNG,
            # but it is still colour-quantized and the transparency is exact.
            alpha = img.getchannel("A")
            low, high = alpha.getextrema()
            if low == high == 255:
                quantized = img.convert("RGB").quantize(
                    colors=colors,
                    method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.FLOYDSTEINBERG,
                )
                notes.append(f"颜色量化至 {colors} 色")
                return quantized
            quantized = img.convert("RGB").quantize(
                colors=colors,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            rgba = quantized.convert("RGBA")
            rgba.putalpha(alpha)
            notes.append(f"颜色量化至 {colors} 色（透明通道保留）")
            return rgba
    except (ValueError, OSError):
        notes.append("该图无法调色板量化，已改用无损压缩")
        return None
    notes.append("该图无法调色板量化，已改用无损压缩")
    return None


def _to_palette(img: Image.Image, background: tuple[int, int, int], notes: list[str]) -> Image.Image:
    """Convert to GIF-friendly P mode, preserving binary transparency."""
    if img.mode in ("P", "1", "L"):
        return img.convert("P", palette=Image.Palette.ADAPTIVE)
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        alpha = rgba.getchannel("A")
        opaque = alpha.point(lambda a: 255 if a >= 128 else 0)
        # Reserve index 255 for fully transparent pixels.
        paletted = _flatten(rgba, background).convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
        palette = paletted.getpalette()
        palette.extend([0, 0, 0] * (256 - len(palette) // 3))
        paletted.putpalette(palette)
        paletted.paste(255, mask=ImageOps.invert(opaque))
        paletted.info["transparency"] = 255
        notes.append("透明通道已转为 GIF 二值透明")
        return paletted
    return img.convert("P", palette=Image.Palette.ADAPTIVE)


def _metadata_kwargs(request: EncodeRequest) -> dict:
    kwargs: dict = {}
    if request.target.supports_icc and request.icc_profile:
        kwargs["icc_profile"] = request.icc_profile
    if request.target.supports_exif and request.exif_bytes:
        kwargs["exif"] = request.exif_bytes
    return kwargs


def _save(img: Image.Image, target_name: str, params: dict, metadata: dict) -> bytes:
    """Save with a single narrow retry: some plugins reject ``exif``/``icc``."""
    buffer = io.BytesIO()
    try:
        img.save(buffer, target_name, **{**params, **metadata})
        return buffer.getvalue()
    except TypeError:
        if not metadata:
            raise
        buffer = io.BytesIO()
        img.save(buffer, target_name, **params)
        return buffer.getvalue()


class PillowEncoder:
    """The always-available encoder."""

    name = "Pillow"

    def available(self) -> bool:
        return True

    def encode(self, request: EncodeRequest) -> EncodeResult:
        target = request.target
        params = {k: v for k, v in request.params.items() if k != "palette_colors"}
        notes = request.notes

        img = _normalize(request.image, request)
        # ``_normalize`` may append notes; keep one list instance.
        notes = request.notes

        if target.key == "png" and request.mode is Mode.LOSSY:
            colors = request.params.get("palette_colors", 256)
            quantized = _quantize_for_png(img, colors, notes)
            if quantized is not None:
                img = quantized
                params = {"compress_level": params.get("compress_level", 9), "optimize": True}

        if target.key == "gif":
            img = _to_palette(img, request.background, notes)
            params = {"optimize": True}

        if target.key == "bmp":
            params = {}

        encoder_name = self.name
        if target.key == "jpeg" and params.get("quality") == "keep":
            # ``quality="keep"`` re-uses the source quantization tables and needs
            # the format marker to still be present after any transposes/copies.
            if getattr(img, "quantization", None) is None or request.source_pillow_format not in ("JPEG", "MPO"):
                params = {"quality": 95, "subsampling": 0, "optimize": True, "progressive": True}
                notes.append("源非 JPEG，已改用 q95 高质量重编码")
            else:
                img.format = "JPEG"
                encoder_name = "Pillow · 视觉无损"

        data = _save(img, target.pillow_name, params, _metadata_kwargs(request))
        return EncodeResult(data=data, encoder=encoder_name, notes=notes)
