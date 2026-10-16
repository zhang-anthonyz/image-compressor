"""Settings persistence: JSON next to the user's app data.

``PIXELPRESS_SETTINGS_DIR`` overrides the location so tests and the offscreen UI
audit never touch the real user profile.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .. import APP_VERSION
from .planner import (
    CollisionPolicy,
    CompressionPlan,
    Effort,
    MetadataPolicy,
    Mode,
    NamingPolicy,
    clamp_quality,
    clamp_scale,
)

ENV_SETTINGS_DIR = "PIXELPRESS_SETTINGS_DIR"
SETTINGS_FILENAME = "settings.json"


def settings_dir() -> Path:
    override = os.environ.get(ENV_SETTINGS_DIR)
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "PixelPress"


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILENAME


def _coerce_enum(enum_cls, value, fallback):
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return fallback


class SettingsStore:
    """Load/save of the persisted plan plus window and app preferences."""

    def __init__(self, plan: CompressionPlan | None = None) -> None:
        self.plan = plan or CompressionPlan()
        self.theme_mode = "light"
        self.window_width = 1280
        self.window_height = 820
        self.last_output_dir = ""
        self.recent_inputs: list[str] = []
        self.show_log = False

    # ------------------------------------------------------------------ io
    def load(self) -> "SettingsStore":
        path = settings_path()
        if not path.is_file():
            return self
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self
        self._apply(payload)
        return self

    def save(self) -> None:
        path = settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.part")
            tmp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        except OSError:
            # A read-only profile must not break the app.
            pass

    def to_dict(self) -> dict:
        plan = self.plan
        return {
            "version": APP_VERSION,
            "theme": self.theme_mode,
            "window": {"width": self.window_width, "height": self.window_height},
            "plan": {
                "mode": plan.mode.value,
                "quality": plan.quality,
                "scale_percent": plan.scale_percent,
                "target_format": plan.target_format,
                "effort": plan.effort.value,
                "metadata": plan.metadata.value,
                "keep_smaller": plan.keep_smaller,
                "background": list(plan.background),
                "naming": plan.naming.value,
                "suffix": plan.suffix,
                "prefix": plan.prefix,
                "template": plan.template,
                "collision": plan.collision.value,
                "out_dir": plan.out_dir,
                "inplace": plan.inplace,
                "workers": plan.workers,
            },
            "last_output_dir": self.last_output_dir,
            "recent_inputs": self.recent_inputs[-10:],
            "show_log": self.show_log,
        }

    def _apply(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        self.theme_mode = payload.get("theme", self.theme_mode)
        window = payload.get("window") or {}
        try:
            self.window_width = int(window.get("width", self.window_width))
            self.window_height = int(window.get("height", self.window_height))
        except (TypeError, ValueError):
            pass

        raw = payload.get("plan") or {}
        plan = self.plan
        plan.mode = _coerce_enum(Mode, raw.get("mode"), plan.mode)
        plan.quality = clamp_quality(raw.get("quality", plan.quality))
        plan.scale_percent = clamp_scale(raw.get("scale_percent", plan.scale_percent))
        target = raw.get("target_format", plan.target_format)
        plan.target_format = target or None
        plan.effort = _coerce_enum(Effort, raw.get("effort"), plan.effort)
        plan.metadata = _coerce_enum(MetadataPolicy, raw.get("metadata"), plan.metadata)
        plan.keep_smaller = bool(raw.get("keep_smaller", plan.keep_smaller))
        background = raw.get("background")
        if isinstance(background, (list, tuple)) and len(background) == 3:
            plan.background = tuple(int(c) for c in background)  # type: ignore[assignment]
        plan.naming = _coerce_enum(NamingPolicy, raw.get("naming"), plan.naming)
        plan.suffix = str(raw.get("suffix", plan.suffix))
        plan.prefix = str(raw.get("prefix", plan.prefix))
        plan.template = str(raw.get("template", plan.template))
        plan.collision = _coerce_enum(CollisionPolicy, raw.get("collision"), plan.collision)
        out_dir = raw.get("out_dir")
        plan.out_dir = str(out_dir) if out_dir else None
        plan.inplace = bool(raw.get("inplace", plan.inplace))
        try:
            plan.workers = max(0, int(raw.get("workers", plan.workers)))
        except (TypeError, ValueError):
            plan.workers = 0

        self.last_output_dir = str(payload.get("last_output_dir", "") or "")
        recent = payload.get("recent_inputs")
        if isinstance(recent, list):
            self.recent_inputs = [str(item) for item in recent][-10:]
        self.show_log = bool(payload.get("show_log", self.show_log))

    def remember_inputs(self, paths) -> None:
        for path in paths:
            text = str(path)
            if text in self.recent_inputs:
                self.recent_inputs.remove(text)
            self.recent_inputs.append(text)
        self.recent_inputs = self.recent_inputs[-10:]
