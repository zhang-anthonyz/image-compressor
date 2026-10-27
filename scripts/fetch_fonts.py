"""Fetch the OFL fonts PixelPress ships with.

Both families are SIL Open Font License 1.1, which permits bundling inside an
application. The app must never depend on the user having them installed: the
sibling tool in this workspace declared Outfit/JetBrains Mono in its stylesheet
and silently fell back to Segoe UI on machines without them.

Run:  python scripts/fetch_fonts.py
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

PROXY = "http://127.0.0.1:7890"
os.environ.setdefault("HTTPS_PROXY", PROXY)
os.environ.setdefault("HTTP_PROXY", PROXY)

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "app" / "assets" / "fonts"
HEADERS = {"User-Agent": "curl/8"}

#: (raw path under google/fonts@main, local file name)
ASSETS: tuple[tuple[str, str], ...] = (
    # The Google-adjacent identity: DM Sans is the closest open relative of
    # Google Sans / Product Sans (geometric, single-story g), and Roboto Mono
    # is Google's own UI mono. Both ship as variable fonts upstream; Qt
    # enumerates their named instances, so one file per family covers
    # Regular → Bold plus the Medium/SemiBold steps the UI uses.
    ("ofl/dmsans/DMSans%5Bopsz%2Cwght%5D.ttf", "DMSans-Variable.ttf"),
    ("ofl/robotomono/RobotoMono%5Bwght%5D.ttf", "RobotoMono-Variable.ttf"),
    ("ofl/dmsans/OFL.txt", "LICENSE-DMSans.txt"),
    ("ofl/robotomono/OFL.txt", "LICENSE-RobotoMono.txt"),
)


def fetch(raw_path: str, destination: Path, *, force: bool = False) -> bool:
    if destination.exists() and not force:
        print(f"  = {destination.name} (present, {destination.stat().st_size / 1024:.0f} KB)")
        return True
    url = f"https://raw.githubusercontent.com/google/fonts/main/{raw_path}"
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except Exception as exc:
        print(f"  ! {destination.name}: {type(exc).__name__}: {exc}")
        return False
    if not payload:
        print(f"  ! {destination.name}: empty response")
        return False
    destination.write_bytes(payload)
    print(f"  + {destination.name} ({len(payload) / 1024:.0f} KB)")
    return True


def main() -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for raw_path, name in ASSETS:
        if not fetch(raw_path, FONT_DIR / name):
            failures += 1
    total = sum(p.stat().st_size for p in FONT_DIR.glob("*.ttf"))
    print(f"\nfonts in {FONT_DIR}: {len(list(FONT_DIR.glob('*.ttf')))} files, {total / 1024:.0f} KB")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
