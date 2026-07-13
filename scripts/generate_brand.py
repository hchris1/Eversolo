"""Generate original Home Assistant brand assets for the integration."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "eversolo" / "brand"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a clean system font with a portable fallback."""
    for path in (
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def _icon(size: int, *, dark: bool) -> Image.Image:
    """Create a stylized E made from three audio wave bars."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    background = (10, 18, 31, 255) if not dark else (238, 248, 255, 255)
    primary = (34, 211, 238, 255) if not dark else (8, 82, 111, 255)
    accent = (59, 130, 246, 255) if not dark else (14, 116, 144, 255)
    margin = round(size * 0.07)
    radius = round(size * 0.22)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=background,
    )

    left = round(size * 0.27)
    top = round(size * 0.27)
    bar_height = max(8, round(size * 0.085))
    gap = round(size * 0.14)
    lengths = (round(size * 0.48), round(size * 0.37), round(size * 0.48))
    for index, length in enumerate(lengths):
        y = top + index * gap
        draw.rounded_rectangle(
            (left, y, left + length, y + bar_height),
            radius=bar_height // 2,
            fill=primary if index != 1 else accent,
        )
    draw.rounded_rectangle(
        (
            left,
            top,
            left + bar_height,
            top + (2 * gap) + bar_height,
        ),
        radius=bar_height // 2,
        fill=primary,
    )
    return image


def _logo(size: tuple[int, int], *, dark: bool) -> Image.Image:
    """Create a horizontal integration logo."""
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    icon_size = round(height * 0.82)
    icon = _icon(icon_size, dark=dark)
    image.alpha_composite(icon, (round(height * 0.09), round(height * 0.09)))
    draw = ImageDraw.Draw(image)
    color = (232, 246, 255, 255) if dark else (10, 18, 31, 255)
    font = _font(round(height * 0.19))
    draw.text(
        (round(height * 0.92), round(height * 0.39)),
        "EVERSOLO",
        font=font,
        fill=color,
        spacing=4,
    )
    return image


def main() -> None:
    """Write all supported local brand variants."""
    BRAND.mkdir(parents=True, exist_ok=True)
    _icon(256, dark=False).save(BRAND / "icon.png", optimize=True)
    _icon(512, dark=False).save(BRAND / "icon@2x.png", optimize=True)
    _icon(256, dark=True).save(BRAND / "dark_icon.png", optimize=True)
    _icon(512, dark=True).save(BRAND / "dark_icon@2x.png", optimize=True)
    _logo((512, 256), dark=False).save(BRAND / "logo.png", optimize=True)
    _logo((1024, 512), dark=False).save(BRAND / "logo@2x.png", optimize=True)
    _logo((512, 256), dark=True).save(BRAND / "dark_logo.png", optimize=True)
    _logo((1024, 512), dark=True).save(BRAND / "dark_logo@2x.png", optimize=True)


if __name__ == "__main__":
    main()
