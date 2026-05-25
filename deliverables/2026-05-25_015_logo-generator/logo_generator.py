"""
AI Studio Accademia Milano — Logo Generator

Generates studio logos in multiple styles and sizes.

Usage:
    python logo_generator.py                          # all styles, default size
    python logo_generator.py --style circle           # one style only
    python logo_generator.py --size 512               # custom size
    python logo_generator.py --accent "#FF6B35"       # custom accent color
    python logo_generator.py --out my_logo.png        # custom output path
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

DEFAULT_BG = "#0A0A0A"
DEFAULT_ACCENT = "#00D4FF"
DEFAULT_TEXT = "#FFFFFF"
DEFAULT_SIZE = 300

OUTPUT_DIR = Path(__file__).parent / "output"


def _font(size: int, bold: bool = True):
    paths = FONT_PATHS if bold else [p.replace("bd", "").replace("Bold", "") for p in FONT_PATHS]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _base(size: int, bg: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (size, size), color=bg)
    return img, ImageDraw.Draw(img)


def logo_circle(size: int, accent: str, bg: str, text_color: str) -> Image.Image:
    img, draw = _base(size, bg)
    pad = size // 30
    draw.ellipse([pad, pad, size - pad, size - pad], outline=accent, width=max(4, size // 50))
    draw.text((size // 2, size * 0.42), "AI", font=_font(size // 3), fill=accent, anchor="mm")
    draw.text((size // 2, size * 0.70), "STUDIO", font=_font(size // 9, bold=False), fill=text_color, anchor="mm")
    return img


def logo_square(size: int, accent: str, bg: str, text_color: str) -> Image.Image:
    img, draw = _base(size, bg)
    pad = size // 20
    r = size // 12
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=r, outline=accent, width=max(4, size // 50))
    draw.text((size // 2, size * 0.42), "AI", font=_font(size // 3), fill=accent, anchor="mm")
    draw.text((size // 2, size * 0.70), "STUDIO", font=_font(size // 9, bold=False), fill=text_color, anchor="mm")
    return img


def logo_minimal(size: int, accent: str, bg: str, text_color: str) -> Image.Image:
    img, draw = _base(size, bg)
    draw.text((size // 2, size * 0.38), "AI", font=_font(size // 3), fill=accent, anchor="mm")
    bar_y = int(size * 0.58)
    bar_w = int(size * 0.55)
    bar_x = (size - bar_w) // 2
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + max(2, size // 80)], fill=accent)
    draw.text((size // 2, size * 0.73), "STUDIO", font=_font(size // 9, bold=False), fill=text_color, anchor="mm")
    return img


STYLES = {
    "circle": logo_circle,
    "square": logo_square,
    "minimal": logo_minimal,
}


def generate(
    style: str = "circle",
    size: int = DEFAULT_SIZE,
    accent: str = DEFAULT_ACCENT,
    bg: str = DEFAULT_BG,
    text_color: str = DEFAULT_TEXT,
    out: Path | None = None,
) -> Path:
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Options: {list(STYLES)}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    img = STYLES[style](size, accent, bg, text_color)
    path = out or OUTPUT_DIR / f"aistudio_logo_{style}_{size}.png"
    img.save(path)
    return Path(path)


def generate_all(size: int = DEFAULT_SIZE, accent: str = DEFAULT_ACCENT) -> list[Path]:
    return [generate(style=s, size=size, accent=accent) for s in STYLES]


def main():
    parser = argparse.ArgumentParser(description="AI Studio Logo Generator")
    parser.add_argument("--style", choices=list(STYLES) + ["all"], default="all")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--accent", default=DEFAULT_ACCENT, help="Accent hex color (default: #00D4FF)")
    parser.add_argument("--bg", default=DEFAULT_BG, help="Background hex color (default: #0A0A0A)")
    parser.add_argument("--text-color", default=DEFAULT_TEXT, help="Text hex color (default: #FFFFFF)")
    parser.add_argument("--out", default=None, help="Output file path (single style only)")
    args = parser.parse_args()

    if args.style == "all":
        paths = generate_all(size=args.size, accent=args.accent)
        for p in paths:
            print(f"  {p}")
    else:
        out = Path(args.out) if args.out else None
        path = generate(style=args.style, size=args.size, accent=args.accent,
                        bg=args.bg, text_color=args.text_color, out=out)
        print(f"  {path}")


if __name__ == "__main__":
    main()
