"""
Generate flyer/ad background images using DALL-E 3.

Usage:
    python generate_flyer.py --copy-file .tmp/output/copy_recruitment_flyer_20240101_120000.json
    python generate_flyer.py --service recruitment --size instagram_square

Input:
    Copy JSON from generate_copy.py (optional)
    .tmp/research/analysis.json (optional — for style guidance)

Output:
    .tmp/output/dalle_{variant}_{size}_{timestamp}.png
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RESEARCH_DIR, OUTPUT_DIR, SERVICE_LINES,
    DALLE_MODEL, DALLE_QUALITY, DALLE_SIZE_MAP, AD_SIZES, DEFAULT_AD_SIZES, BRAND,
)
from utils import get_openai_client, download_image, save_json, load_json, timestamp


def build_dalle_prompt(
    service_key: str,
    ad_size_name: str,
    copy_variant: dict = None,
    visual_analysis: dict = None,
) -> str:
    """Build a detailed DALL-E prompt based on copy and research."""
    service = SERVICE_LINES[service_key]

    # Base style direction
    style_notes = ""
    if visual_analysis:
        colors = visual_analysis.get("color_patterns", {})
        layout = visual_analysis.get("layout_patterns", {})
        imagery = visual_analysis.get("imagery_patterns", {})
        style_notes = f"""
Style direction from research:
- Colors: {', '.join(colors.get('primary_colors', ['navy blue', 'white']))}
- Layout: {', '.join(layout.get('common_layouts', ['clean, modern']))}
- Imagery: {', '.join(imagery.get('photo_subjects', ['professional people', 'office settings']))}"""

    # Copy-informed visual direction
    copy_context = ""
    if copy_variant:
        angle = copy_variant.get("angle", "professional")
        headline = copy_variant.get("headline", "")
        copy_context = f"""
The ad communicates: "{headline}"
The creative angle is: {angle}
Leave clear space for text overlay — do NOT include any text, words, letters, or numbers in the image."""

    w, h = AD_SIZES[ad_size_name]
    orientation = "square" if w == h else ("landscape" if w > h else "portrait")

    prompt = f"""Create a professional, modern {orientation} background image for a {service['name']} advertisement.

REQUIREMENTS:
- Clean, corporate design suitable for a recruitment/HR company
- Brand colors: {BRAND['primary_color']} (navy) as primary, {BRAND['accent_color']} (green) as accent
- Professional, trustworthy feel
- Abstract geometric shapes or subtle patterns (NOT clip art)
- Leave large clear areas for text overlay (top 40% and bottom 20% should be text-friendly)
- Do NOT include ANY text, letters, words, numbers, or typography
- High contrast areas where white or dark text would be readable
- Modern, clean design — think premium B2B marketing
{style_notes}
{copy_context}

Style: Photorealistic corporate design with clean gradients, professional lighting, subtle depth.
NOT: Cartoonish, clip art, busy patterns, stock photo clichés."""

    return prompt


def generate_dalle_image(prompt: str, size: str = "1024x1024") -> str:
    """Generate an image with DALL-E and return the URL."""
    client = get_openai_client()

    response = client.images.generate(
        model=DALLE_MODEL,
        prompt=prompt,
        size=size,
        quality=DALLE_QUALITY,
        n=1,
    )

    return response.data[0].url


def main():
    parser = argparse.ArgumentParser(description="Generate ad images with DALL-E")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment")
    parser.add_argument("--copy-file", type=str, default="", help="Path to copy JSON from generate_copy.py")
    parser.add_argument("--size", choices=list(AD_SIZES.keys()), nargs="+", default=DEFAULT_AD_SIZES)
    parser.add_argument("--variants", type=int, default=1, help="Which copy variants to generate for (0=all)")
    args = parser.parse_args()

    service = SERVICE_LINES[args.service]
    ts = timestamp()
    print(f"Generating DALL-E images for: {service['name']}")

    # Load copy if provided
    copy_variants = [None]
    if args.copy_file and Path(args.copy_file).exists():
        copy_data = load_json(args.copy_file)
        copy_variants = copy_data.get("variants", [None])
        if args.variants > 0:
            copy_variants = copy_variants[:args.variants]
        print(f"  Using {len(copy_variants)} copy variant(s)")

    # Load visual research if available
    analysis_path = RESEARCH_DIR / "analysis.json"
    visual_analysis = None
    if analysis_path.exists():
        analysis = load_json(analysis_path)
        visual_analysis = analysis.get("visual_analysis")
        print("  Using visual research for style direction")

    # Generate images
    generated = []
    for v_idx, variant in enumerate(copy_variants):
        for size_name in args.size:
            dalle_size = DALLE_SIZE_MAP.get(size_name, "1024x1024")
            print(f"\n  Generating: variant {v_idx+1}, size {size_name} ({dalle_size})")

            prompt = build_dalle_prompt(
                service_key=args.service,
                ad_size_name=size_name,
                copy_variant=variant,
                visual_analysis=visual_analysis,
            )

            try:
                image_url = generate_dalle_image(prompt, size=dalle_size)
                filename = f"dalle_v{v_idx+1}_{size_name}_{ts}.png"
                save_path = OUTPUT_DIR / filename
                download_image(image_url, save_path)

                generated.append({
                    "variant": v_idx + 1,
                    "size_name": size_name,
                    "dalle_size": dalle_size,
                    "file": str(save_path),
                    "prompt": prompt,
                })
                print(f"    Saved: {filename}")

            except Exception as e:
                print(f"    ERROR: {e}")

    # Save generation manifest
    manifest = {
        "service": args.service,
        "timestamp": ts,
        "total_generated": len(generated),
        "images": generated,
    }
    manifest_path = OUTPUT_DIR / f"dalle_manifest_{ts}.json"
    save_json(manifest, manifest_path)
    print(f"\nGenerated {len(generated)} images. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
