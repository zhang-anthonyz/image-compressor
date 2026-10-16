"""Format registry behaviour."""
from __future__ import annotations

from app.core import formats


def test_detect_by_extension_is_case_insensitive(tmp_path):
    assert formats.detect(tmp_path / "a.JPG").key == "jpeg"
    assert formats.detect(tmp_path / "a.JPEG").key == "jpeg"
    assert formats.detect(tmp_path / "a.webp").key == "webp"
    assert formats.detect(tmp_path / "a.heic").key == "heic"
    assert formats.detect(tmp_path / "a.txt") is None


def test_jpeg_aliases_map_to_one_spec():
    assert formats.detect("x.jfif").key == "jpeg"
    assert formats.detect("x.jpe").key == "jpeg"
    assert len({f.key for f in formats.ALL_FORMATS}) == len(formats.ALL_FORMATS)


def test_pillow_name_mapping_includes_mpo_alias():
    assert formats.spec_for_pillow_name("MPO").key == "jpeg"
    assert formats.spec_for_pillow_name("WEBP").key == "webp"
    assert formats.spec_for_pillow_name(None) is None
    assert formats.spec_for_pillow_name("NOPE") is None


def test_target_picker_only_offers_writable_formats():
    for spec in formats.writable_specs():
        assert spec.can_write is True
    keys = {spec.key for spec in formats.writable_specs()}
    assert "heic" not in keys, "HEIC is decode-only by design"
    assert {"jpeg", "png", "webp", "avif"} <= keys


def test_avif_advertises_no_lossless_and_says_why():
    avif = formats.BY_KEY["avif"]
    assert avif.can_lossless is False
    assert "无损" in avif.lossless_note


def test_gif_and_bmp_have_no_lossless_knob():
    assert formats.BY_KEY["gif"].can_lossless is False
    assert formats.BY_KEY["bmp"].can_lossy is False


def test_dialog_extensions_cover_every_registered_extension():
    for spec in formats.ALL_FORMATS:
        for ext in spec.extensions:
            assert ext in formats.DIALOG_EXTENSIONS
