"""Output path resolution: naming rules, format-driven extensions, collisions.

Two collision classes are handled differently on purpose:

* **existing file on disk** — the user's chosen policy applies
  (auto-rename / skip / overwrite);
* **another file in the same batch** — always auto-renamed, because two source
  files silently clobbering each other is never what anyone wants, even when
  overwrite is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .formats import FormatSpec
from .planner import CompressionPlan, NamingPolicy


@dataclass
class Resolution:
    """Where a file should be written, or why it should not be."""

    path: Path | None
    skip_reason: str = ""
    renamed: bool = False


def _apply_naming(plan: CompressionPlan, source: Path, width: int, height: int) -> str:
    """Stem for the output file, per the naming policy."""
    if plan.naming is NamingPolicy.PREFIX:
        return f"{plan.prefix}{source.stem}"
    if plan.naming is NamingPolicy.TEMPLATE:
        template = plan.template or "{name}_min"
        try:
            return template.format(
                name=source.stem,
                ext=source.suffix.lstrip("."),
                width=width,
                height=height,
                quality=plan.quality,
            )
        except (KeyError, IndexError, ValueError):
            # A malformed template must not lose the file: fall back to suffix.
            return f"{source.stem}{plan.suffix or '_min'}"
    return f"{source.stem}{plan.suffix}"


def unique_path(path: Path, taken: set[Path], *, avoid_existing: bool = True) -> Path:
    """``a.jpg`` -> ``a (1).jpg`` until the name is free.

    ``taken`` covers names already claimed earlier in this batch; with
    ``avoid_existing`` the filesystem is checked too (a name can be occupied by
    a file that is not part of this run at all).
    """

    def is_taken(candidate: Path) -> bool:
        if candidate in taken:
            return True
        return avoid_existing and candidate.exists()

    counter = 1
    candidate = path
    while is_taken(candidate):
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        counter += 1
    return candidate


def resolve_output(
    source: Path,
    plan: CompressionPlan,
    target: FormatSpec,
    *,
    out_dir: Path | None = None,
    taken: set[Path] | None = None,
    width: int = 0,
    height: int = 0,
) -> Resolution:
    """Resolve the destination path for ``source`` under ``plan``."""
    taken = taken if taken is not None else set()

    if plan.inplace:
        if plan.target_format and plan.target_format != source.suffix.lstrip(".").lower():
            # Overwriting in place while also changing format would leave the
            # user with a differently-named file and a stale original.
            return Resolution(
                None,
                skip_reason="原地覆盖模式下不能同时转换格式（请关闭其一）",
            )
        return Resolution(source)

    stem = _apply_naming(plan, source, width, height)
    extension = f".{target.key}" if target.key != "jpeg" else ".jpg"
    # Prefer a familiar extension for the container when the source used one.
    for candidate_ext in target.extensions:
        if source.suffix.lower() == candidate_ext:
            extension = candidate_ext
            break
    directory = out_dir if out_dir is not None else source.parent
    destination = directory / f"{stem}{extension}"

    if destination in taken:
        return Resolution(unique_path(destination, taken), renamed=True)

    if destination.exists():
        if destination.resolve() == source.resolve():
            return Resolution(unique_path(destination, taken), renamed=True)
        if plan.collision.value == "skip":
            return Resolution(None, skip_reason="输出文件已存在")
        if plan.collision.value == "overwrite":
            return Resolution(destination)
        return Resolution(unique_path(destination, taken), renamed=True)

    return Resolution(destination)


def default_out_dir(plan: CompressionPlan, sources: list[Path]) -> Path | None:
    """The folder the UI should show as the current destination."""
    if plan.inplace:
        return None
    if plan.out_dir:
        return Path(plan.out_dir)
    if sources:
        return sources[0].parent / "compressed"
    return None
