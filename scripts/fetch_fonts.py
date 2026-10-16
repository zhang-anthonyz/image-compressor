"""Fetch the OFL fonts PixelPress ships with.

Both families are SIL Open Font License 1.1, which permits bundling inside an
application. The app must never depend on the user having them installed: the
sibling tool in this workspace declared Outfit/JetBrains Mono in its stylesheet
and silently fell back to Segoe UI on machines without them.

Run:  python scripts/fetch_fonts.py
"""
from __future__ import annotations

import json
import os
import urllib.parse
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
    # Archivo ships as a variable font upstream; Qt 6.12 enumerates its nine
    # named instances, so one 643 KB file covers Regular → Black.
    ("ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf", "Archivo-Variable.ttf"),
    ("ofl/ibmplexmono/IBMPlexMono-Regular.ttf", "IBMPlexMono-Regular.ttf"),
    ("ofl/ibmplexmono/IBMPlexMono-Medium.ttf", "IBMPlexMono-Medium.ttf"),
    ("ofl/ibmplexmono/IBMPlexMono-SemiBold.ttf", "IBMPlexMono-SemiBold.ttf"),
    ("ofl/archivo/OFL.txt", "LICENSE-Archivo.txt"),
    ("ofl/ibmplexmono/OFL.txt", "LICENSE-IBMPlexMono.txt"),
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
