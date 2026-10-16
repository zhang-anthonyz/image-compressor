"""Output naming, collisions, in-place mode."""
from __future__ import annotations

from pathlib import Path

from app.core import formats
from app.core.naming import resolve_output, unique_path
from app.core.planner import CollisionPolicy, CompressionPlan, NamingPolicy

PNG = formats.BY_KEY["png"]
JPEG = formats.BY_KEY["jpeg"]


def test_suffix_naming_keeps_the_source_extension(tmp_path):
    source = tmp_path / "shot.png"
    plan = CompressionPlan(naming=NamingPolicy.SUFFIX, suffix="_min")
    resolution = resolve_output(source, plan, PNG)
    assert resolution.path == tmp_path / "shot_min.png"


def test_jpeg_output_prefers_jpg(tmp_path):
    source = tmp_path / "photo.PNG"
    plan = CompressionPlan(naming=NamingPolicy.SUFFIX, suffix="_min", target_format="jpeg")
    assert resolve_output(source, plan, JPEG).path.suffix == ".jpg"


def test_existing_jpg_extension_is_kept(tmp_path):
    source = tmp_path / "photo.jpeg"
    plan = CompressionPlan(naming=NamingPolicy.SUFFIX, target_format="jpeg")
    assert resolve_output(source, plan, JPEG).path.name == "photo_min.jpeg"


def test_prefix_naming(tmp_path):
    source = tmp_path / "shot.png"
    plan = CompressionPlan(naming=NamingPolicy.PREFIX, prefix="min_")
    assert resolve_output(source, plan, PNG).path.name == "min_shot.png"


def test_template_naming_uses_dimensions(tmp_path):
    source = tmp_path / "shot.png"
    plan = CompressionPlan(naming=NamingPolicy.TEMPLATE, template="{name}_{width}x{height}")
    resolution = resolve_output(source, plan, PNG, width=1920, height=1080)
    assert resolution.path.name == "shot_1920x1080.png"


def test_broken_template_falls_back_instead_of_failing(tmp_path):
    source = tmp_path / "shot.png"
    plan = CompressionPlan(naming=NamingPolicy.TEMPLATE, template="{nope}", suffix="_min")
    assert resolve_output(source, plan, PNG).path.name == "shot_min.png"


def test_out_dir_is_honoured(tmp_path):
    source = tmp_path / "sub" / "shot.png"
    plan = CompressionPlan(naming=NamingPolicy.SUFFIX)
    destination = tmp_path / "elsewhere"
    resolution = resolve_output(source, plan, PNG, out_dir=destination)
    assert resolution.path.parent == destination


def test_collision_auto_renames_by_default(tmp_path):
    source = tmp_path / "shot.png"
    existing = tmp_path / "shot_min.png"
    existing.write_bytes(b"taken")
    plan = CompressionPlan(collision=CollisionPolicy.RENAME)
    resolution = resolve_output(source, plan, PNG)
    assert resolution.renamed and resolution.path.name == "shot_min (1).png"


def test_collision_skip_reports_a_reason(tmp_path):
    source = tmp_path / "shot.png"
    (tmp_path / "shot_min.png").write_bytes(b"taken")
    plan = CompressionPlan(collision=CollisionPolicy.SKIP)
    resolution = resolve_output(source, plan, PNG)
    assert resolution.path is None and "已存在" in resolution.skip_reason


def test_collision_overwrite_reuses_the_name(tmp_path):
    source = tmp_path / "shot.png"
    existing = tmp_path / "shot_min.png"
    existing.write_bytes(b"taken")
    plan = CompressionPlan(collision=CollisionPolicy.OVERWRITE)
    assert resolve_output(source, plan, PNG).path == existing


def test_two_sources_in_one_batch_never_clobber_each_other(tmp_path):
    """Even with overwrite enabled, within-batch collisions auto-rename."""
    first = tmp_path / "a" / "shot.png"
    second = tmp_path / "b" / "shot.png"
    shared = tmp_path / "out"
    shared.mkdir()
    plan = CompressionPlan(collision=CollisionPolicy.OVERWRITE)
    taken: set[Path] = set()

    first_out = resolve_output(first, plan, PNG, out_dir=shared, taken=taken)
    taken.add(first_out.path)
    second_out = resolve_output(second, plan, PNG, out_dir=shared, taken=taken)

    assert first_out.path != second_out.path
    assert second_out.renamed
    assert second_out.path.name == "shot_min (1).png"


def test_source_is_never_overwritten_by_accident(tmp_path):
    """Same folder + same name would be the source itself: always rename."""
    source = tmp_path / "shot.png"
    source.write_bytes(b"original")
    plan = CompressionPlan(naming=NamingPolicy.TEMPLATE, template="{name}")
    resolution = resolve_output(source, plan, PNG)
    assert resolution.path != source and resolution.renamed
    assert resolution.path.name == "shot (1).png"


def test_inplace_mode_targets_the_source(tmp_path):
    source = tmp_path / "shot.png"
    plan = CompressionPlan(inplace=True)
    assert resolve_output(source, plan, PNG).path == source


def test_inplace_with_format_change_is_refused(tmp_path):
    source = tmp_path / "shot.png"
    plan = CompressionPlan(inplace=True, target_format="webp")
    resolution = resolve_output(source, plan, PNG)
    assert resolution.path is None and "格式" in resolution.skip_reason


def test_unique_path_counts_up(tmp_path):
    target = tmp_path / "a.png"
    taken = {target, tmp_path / "a (1).png"}
    assert unique_path(target, taken).name == "a (2).png"
