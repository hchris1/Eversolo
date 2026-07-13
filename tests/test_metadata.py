"""Validate repository metadata and bundled integration assets."""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "eversolo"


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object."""
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    assert isinstance(value, dict)
    return value


def _shape(value: Any) -> Any:
    """Return a translation tree's key shape."""
    if isinstance(value, dict):
        return {key: _shape(child) for key, child in value.items()}
    return None


def _png_size(path: Path) -> tuple[int, int]:
    """Read PNG dimensions without an image dependency."""
    with path.open("rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"
        length = struct.unpack(">I", image.read(4))[0]
        assert image.read(4) == b"IHDR"
        assert length == 13
        return struct.unpack(">II", image.read(8))


def test_manifest_is_modern_and_pinned() -> None:
    """Runtime metadata points at the fork and pins its sole dependency."""
    manifest = _load_json(INTEGRATION / "manifest.json")
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", manifest["version"])
    assert manifest["requirements"] == ["wakeonlan==4.0.0"]
    assert manifest["documentation"] == "https://github.com/TheFab21/Eversolo"
    assert manifest["zeroconf"] == ["_eversolo._tcp.local."]


def test_translation_shapes_match() -> None:
    """English, French, and source strings contain the same keys."""
    strings = _load_json(INTEGRATION / "strings.json")
    english = _load_json(INTEGRATION / "translations" / "en.json")
    french = _load_json(INTEGRATION / "translations" / "fr.json")
    assert strings == english
    assert _shape(french) == _shape(strings)


def test_brand_assets_have_expected_dimensions() -> None:
    """Local brand variants meet consistent standard and @2x dimensions."""
    brand = INTEGRATION / "brand"
    expected = {
        "icon.png": (256, 256),
        "icon@2x.png": (512, 512),
        "dark_icon.png": (256, 256),
        "dark_icon@2x.png": (512, 512),
        "logo.png": (512, 256),
        "logo@2x.png": (1024, 512),
        "dark_logo.png": (512, 256),
        "dark_logo@2x.png": (1024, 512),
    }
    assert {path.name: _png_size(path) for path in brand.glob("*.png")} == expected
