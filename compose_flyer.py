"""
Compose final flyers by overlaying generated copy onto DALL-E backgrounds using Pillow.

Usage:
    python compose_flyer.py --background .tmp/output/dalle_v1_instagram_square_*.png --copy-file .tmp/output/copy_*.json
    python compose_flyer.py --manifest .tmp/output/dalle_manifest_*.json --copy-file .tmp/output/copy_*.json

Output:
    .tmp/output/final/flyer_{variant}_{size}_{timestamp}.png
"""

import argparse
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import OUTPUT_DIR, FINAL_DIR, AD_SIZES, BRAND
from utils import load_json, save_json, timestamp

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ── Typography Config ──────────────────────────────────────────────────

FONT_PATHS = {
    "heading": ["arialbd.ttf", "Arial Bold.ttf", "Impact.ttf"],
    "body": ["arial.ttf", "Arial.ttf", "Helvetica.ttf"],
}


def load_font(style: str, size: int) -> ImageFont.FreeTypeFont:
    """Try to load a font, falling back gracefully."""
    candidates = FONT_PATHS.get(style, FONT_PATHS["body"])
    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    """Convert hex color to RGBA tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)


# ── Text Layout Engine ─────────────────────────────────────────────────

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = font.getbbox(test_line)
        if bbox[2] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)
    return lines


def draw_text_block(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: int, y: int,
    max_width: int,
    color: tuple = (255, 255, 255, 255),
    line_spacing: float = 1.3,
    align: str = "left",
    shadow: bool = True,
) -> int:
    """Draw a block of wrapped text. Returns the Y position after the block."""
    lines = wrap_text(text, font, max_width)
    bbox = font.getbbox("Ag")
    line_height = int((bbox[3] - bbox[1]) * line_spacing)

    for line in lines:
        line_bbox = font.getbbox(line)
        line_width = line_bbox[2] - line_bbox[0]

        if align == "center":
            lx = x + (max_width - line_width) // 2
        elif align == "right":
            lx = x + max_width - line_width
        else:
            lx = x

        # Drop shadow for readability
        if shadow:
            draw.text((lx + 2, y + 2), line, fill=(0, 0, 0, 160), font=font)

        draw.text((lx, y), line, fill=color, font=font)
        y += line_height

    return y


# ── Overlay Composition ────────────────────────────────────────────────

def add_gradient_overlay(img: Image.Image, direction: str = "bottom", opacity: float = 0.6) -> Image.Image:
    """Add a gradient overlay for text readability."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size

    if direction == "bottom":
        for y in range(h // 3, h):
            progress = (y - h // 3) / (h * 2 // 3)
            alpha = int(255 * opacity * progress)
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    elif direction == "top":
        for y in range(0, h * 2 // 3):
            progress = 1 - (y / (h * 2 // 3))
            alpha = int(255 * opacity * progress)
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    elif direction == "full":
        for y in range(h):
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, int(255 * opacity * 0.5)))

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def add_accent_bar(img: Image.Image, y: int, height: int = 6, color: str = None) -> Image.Image:
    """Add a colored accent bar across the image."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bar_color = hex_to_rgba(color or BRAND["secondary_color"], 220)
    draw.rectangle([(0, y), (img.width, y + height)], fill=bar_color)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def compose_flyer(
    background_path: str,
    copy_variant: dict,
    output_path: str,
    target_size: tuple[int, int] = None,
) -> Path:
    """Compose a complete flyer from background + copy."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load and resize background
    bg = Image.open(background_path).convert("RGBA")
    if target_size:
        bg = bg.resize(target_size, Image.LANCZOS)

    w, h = bg.size
    margin = int(w * 0.08)
    text_width = w - (margin * 2)

    # Add gradient overlay for text readability
    img = add_gradient_overlay(bg, direction="bottom", opacity=0.65)
    img = add_gradient_overlay(img, direction="top", opacity=0.4)

    draw = ImageDraw.Draw(img)

    # Calculate font sizes relative to image
    headline_size = max(int(h * 0.06), 36)
    sub_size = max(int(h * 0.035), 24)
    body_size = max(int(h * 0.028), 18)
    cta_size = max(int(h * 0.04), 28)
    bullet_size = max(int(h * 0.025), 16)

    headline_font = load_font("heading", headline_size)
    sub_font = load_font("body", sub_size)
    body_font = load_font("body", body_size)
    cta_font = load_font("heading", cta_size)
    bullet_font = load_font("body", bullet_size)

    white = (255, 255, 255, 255)
    accent = hex_to_rgba(BRAND["accent_color"])
    light_gray = (220, 220, 220, 255)

    # ── Layout: Top section (headline + sub) ──
    y = int(h * 0.12)

    headline = copy_variant.get("headline", "")
    if headline:
        y = draw_text_block(draw, headline.upper(), headline_font, margin, y, text_width,
                           color=white, align="left", line_spacing=1.2)
        y += int(h * 0.02)

    # Accent bar
    img = add_accent_bar(img, y, height=max(4, int(h * 0.005)))
    draw = ImageDraw.Draw(img)
    y += int(h * 0.03)

    subheadline = copy_variant.get("subheadline", "")
    if subheadline:
        y = draw_text_block(draw, subheadline, sub_font, margin, y, text_width,
                           color=light_gray, align="left")
        y += int(h * 0.03)

    # ── Middle section (body + bullets) ──
    body = copy_variant.get("body", "")
    if body:
        y = draw_text_block(draw, body, body_font, margin, y, text_width,
                           color=light_gray, align="left")
        y += int(h * 0.02)

    bullets = copy_variant.get("bullet_points", [])
    for bullet in bullets:
        bullet_text = f"  •  {bullet}"
        y = draw_text_block(draw, bullet_text, bullet_font, margin, y, text_width,
                           color=white, align="left", line_spacing=1.5)

    # ── Bottom section (CTA) ──
    cta = copy_variant.get("cta", "")
    if cta:
        cta_y = int(h * 0.82)
        # CTA button background
        cta_bbox = cta_font.getbbox(cta.upper())
        cta_w = cta_bbox[2] - cta_bbox[0] + int(w * 0.08)
        cta_h = cta_bbox[3] - cta_bbox[1] + int(h * 0.03)
        cta_x = margin

        # Draw rounded-ish CTA button
        btn_color = hex_to_rgba(BRAND["secondary_color"], 230)
        draw.rounded_rectangle(
            [(cta_x, cta_y), (cta_x + cta_w, cta_y + cta_h)],
            radius=int(cta_h * 0.3),
            fill=btn_color,
        )
        # CTA text centered in button
        draw.text(
            (cta_x + int(w * 0.04), cta_y + int(h * 0.008)),
            cta.upper(),
            fill=white,
            font=cta_font,
        )

    # ── Tagline at bottom ──
    tagline = copy_variant.get("tagline", "")
    if tagline:
        tagline_font = load_font("body", max(int(h * 0.02), 14))
        tagline_y = int(h * 0.93)
        draw_text_block(draw, tagline, tagline_font, margin, tagline_y, text_width,
                       color=light_gray, align="left", shadow=False)

    # Save
    img.convert("RGB").save(str(output_path), quality=95)
    print(f"  Composed: {output_path.name}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Compose final flyers from backgrounds + copy")
    parser.add_argument("--manifest", type=str, help="Path to DALL-E manifest JSON")
    parser.add_argument("--background", type=str, help="Path to a single background image")
    parser.add_argument("--copy-file", type=str, required=True, help="Path to copy JSON")
    parser.add_argument("--variant", type=int, default=0, help="Copy variant index (0=all)")
    args = parser.parse_args()

    ts = timestamp()

    # Load copy
    copy_data = load_json(args.copy_file)
    variants = copy_data.get("variants", [])
    if args.variant > 0:
        variants = [v for v in variants if v.get("variant_number") == args.variant]
    print(f"Using {len(variants)} copy variant(s)")

    # Get background images
    backgrounds = []
    if args.manifest:
        manifest = load_json(args.manifest)
        backgrounds = [(img["file"], img.get("size_name")) for img in manifest.get("images", [])]
    elif args.background:
        backgrounds = [(args.background, None)]
    else:
        print("ERROR: Provide either --manifest or --background")
        sys.exit(1)

    print(f"Using {len(backgrounds)} background image(s)")

    composed = []
    for bg_path, size_name in backgrounds:
        target_size = AD_SIZES.get(size_name) if size_name else None
        for variant in variants:
            v_num = variant.get("variant_number", 1)
            size_label = size_name or "custom"
            filename = f"flyer_v{v_num}_{size_label}_{ts}.png"
            output_path = FINAL_DIR / filename

            result = compose_flyer(
                background_path=bg_path,
                copy_variant=variant,
                output_path=str(output_path),
                target_size=target_size,
            )
            composed.append({"file": str(result), "variant": v_num, "size": size_label})

    # Save composition manifest
    comp_manifest = {
        "timestamp": ts,
        "total_composed": len(composed),
        "flyers": composed,
    }
    save_json(comp_manifest, FINAL_DIR / f"compose_manifest_{ts}.json")
    print(f"\nComposed {len(composed)} final flyers in {FINAL_DIR}")


if __name__ == "__main__":
    main()
