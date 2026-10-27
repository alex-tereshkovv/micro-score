"""Build the raster assets for the public Senim Risk identity.

The source-of-truth vector mark lives in ``apps/web/assets/senim-risk-mark.svg``.
This script produces the favicon, application icon, wordmark lockup, and social
preview used by the website, PDFs, and repository presentation.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "apps" / "web" / "assets"

INK = "#10252d"
INK_SOFT = "#29444c"
TEAL = "#12b8a6"
TEAL_DARK = "#078f86"
AMBER = "#f5ad2f"
WHITE = "#f7fbfa"
MUTED = "#afc2c4"


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    windows = Path("C:/Windows/Fonts")
    candidates = [
        windows / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        windows / ("arialbd.ttf" if bold else "arial.ttf"),
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size=size)
        except OSError:
            continue
    raise RuntimeError("No suitable TrueType font was found for the brand assets")


def _vertical_gradient(size: tuple[int, int], start: str, end: str) -> Image.Image:
    width, height = size
    start_rgb = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        mix = y / max(height - 1, 1)
        color = tuple(round(a + (b - a) * mix) for a, b in zip(start_rgb, end_rgb))
        draw.line((0, y, width, y), fill=color)
    return image


def build_mark(size: int) -> Image.Image:
    """Render the compact trust-and-horizon mark at a requested square size."""

    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def point(x: float, y: float) -> tuple[int, int]:
        return round(x * canvas_size), round(y * canvas_size)

    draw.rounded_rectangle(
        (point(0.03, 0.03), point(0.97, 0.97)),
        radius=round(0.19 * canvas_size),
        fill=INK,
        outline="#31505a",
        width=round(0.008 * canvas_size),
    )
    draw.arc(
        (point(0.22, 0.19), point(0.78, 0.69)),
        start=180,
        end=360,
        fill=AMBER,
        width=round(0.07 * canvas_size),
    )
    draw.polygon(
        [point(0.09, 0.70), point(0.34, 0.43), point(0.53, 0.70)],
        fill=WHITE,
    )
    draw.line(
        [point(0.34, 0.58), point(0.51, 0.39), point(0.79, 0.70)],
        fill=TEAL,
        width=round(0.11 * canvas_size),
        joint="curve",
    )
    draw.line(
        [point(0.68, 0.63), point(0.82, 0.50), point(0.95, 0.70)],
        fill=WHITE,
        width=round(0.10 * canvas_size),
        joint="curve",
    )
    draw.line(
        [point(0.34, 0.82), point(0.66, 0.82)],
        fill=AMBER,
        width=round(0.035 * canvas_size),
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def build_lockup() -> Image.Image:
    image = Image.new("RGBA", (1400, 360), (0, 0, 0, 0))
    mark = build_mark(300)
    image.alpha_composite(mark, (24, 30))
    draw = ImageDraw.Draw(image)
    name_font = _font(112, bold=True)
    subtitle_font = _font(38, bold=False)
    x = 372
    y = 62
    draw.text((x, y), "Senim", fill=INK, font=name_font)
    senim_width = draw.textlength("Senim", font=name_font)
    draw.text((x + senim_width + 18, y), "Risk", fill=TEAL_DARK, font=name_font)
    draw.text(
        (x + 4, 208),
        "AN INTERPRETABLE CREDIT-RISK SYSTEM",
        fill=INK_SOFT,
        font=subtitle_font,
    )
    return image


def build_social_preview() -> Image.Image:
    image = _vertical_gradient((1200, 630), "#0c222a", "#123c42").convert("RGBA")
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((790, -240, 1330, 300), fill=(18, 184, 166, 42))
    glow_draw.ellipse((-210, 420, 390, 920), fill=(245, 173, 47, 28))
    image = Image.alpha_composite(image, glow)

    draw = ImageDraw.Draw(image)
    mark = build_mark(218)
    image.alpha_composite(mark, (80, 78))
    name_font = _font(104, bold=True)
    subtitle_font = _font(43)
    meta_font = _font(28, bold=True)
    body_font = _font(28)
    x = 350
    y = 89
    draw.text((x, y), "Senim", fill=WHITE, font=name_font)
    senim_width = draw.textlength("Senim", font=name_font)
    draw.text((x + senim_width + 17, y), "Risk", fill=TEAL, font=name_font)
    draw.rounded_rectangle((350, 229, 1070, 235), radius=3, fill=TEAL)
    draw.text(
        (350, 271),
        "An interpretable credit-risk system",
        fill=WHITE,
        font=subtitle_font,
    )
    draw.text((350, 326), "for thin-file borrowers.", fill=WHITE, font=subtitle_font)

    draw.rounded_rectangle(
        (80, 468, 1120, 552),
        radius=24,
        fill=(6, 29, 35, 216),
        outline=(255, 255, 255, 55),
        width=2,
    )
    draw.text((116, 490), "PAVLODAR", fill=AMBER, font=meta_font)
    draw.text((342, 491), "Human review", fill=WHITE, font=body_font)
    draw.text((606, 491), "Monte Carlo", fill=WHITE, font=body_font)
    draw.text((850, 491), "Synthetic demo", fill=MUTED, font=body_font)
    return image.convert("RGB")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_mark(32).save(ASSETS / "favicon-32.png", optimize=True)
    build_mark(180).save(ASSETS / "apple-touch-icon.png", optimize=True)
    build_mark(512).save(ASSETS / "senim-risk-mark.png", optimize=True)
    build_lockup().save(ASSETS / "senim-risk-lockup.png", optimize=True)
    build_social_preview().save(ASSETS / "senim-risk-social-preview.png", optimize=True)
    print("Senim Risk brand assets generated")


if __name__ == "__main__":
    main()
