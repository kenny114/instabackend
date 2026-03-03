"""
Analyze collected ads using GPT-4 to identify patterns and best practices.

Usage:
    python analyze_ads.py [--service recruitment|performance_management|learning_development]

Input:
    .tmp/research/meta_ads.json
    .tmp/research/web_ads.json

Output:
    .tmp/research/analysis.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RESEARCH_DIR, SERVICE_LINES
from utils import chat_completion, vision_analysis, load_json, save_json, timestamp


ANALYSIS_SYSTEM_PROMPT = """You are an expert advertising analyst specializing in recruitment and HR services marketing.
Analyze the provided ads and extract actionable patterns. Be specific with colors (hex codes),
font styles, layout structures, and messaging strategies. Focus on what makes recruitment ads effective."""


def analyze_ad_copy(ads_data: list[dict], service_name: str) -> dict:
    """Analyze ad copy patterns using GPT-4."""
    # Extract all copy from collected ads
    all_copy = []
    for ad in ads_data:
        bodies = ad.get("bodies", [])
        titles = ad.get("titles", [])
        descriptions = ad.get("descriptions", [])
        snippets = [ad.get("snippet", "")] if ad.get("snippet") else []
        all_copy.append({
            "source": ad.get("source", "unknown"),
            "titles": titles,
            "bodies": bodies,
            "descriptions": descriptions + snippets,
        })

    prompt = f"""Analyze these {len(all_copy)} recruitment/HR ad examples for a {service_name} service.

AD DATA:
{json.dumps(all_copy[:30], indent=2)}

Return a JSON object with this exact structure:
{{
    "headline_patterns": {{
        "common_structures": ["list of 5 headline formulas that appear most"],
        "power_words": ["list of 10 most effective words used"],
        "avg_length": "typical headline word count",
        "best_examples": ["top 3 most compelling headlines found"]
    }},
    "body_copy_patterns": {{
        "tone": "description of the dominant tone",
        "common_themes": ["list of 5 recurring themes"],
        "cta_phrases": ["list of 5 most used call-to-action phrases"],
        "avg_length": "typical body copy word count",
        "best_examples": ["top 3 most compelling body texts found"]
    }},
    "messaging_strategy": {{
        "value_propositions": ["what benefits are highlighted most"],
        "pain_points_addressed": ["what problems the ads solve"],
        "emotional_triggers": ["what emotions the ads target"],
        "differentiation": ["how top ads stand out from generic ones"]
    }},
    "recommendations": {{
        "do": ["5 things the best ads do"],
        "avoid": ["5 things to avoid based on weak ads"]
    }}
}}"""

    response = chat_completion(prompt, system=ANALYSIS_SYSTEM_PROMPT, json_mode=True)
    return json.loads(response)


def analyze_visual_patterns(images_data: list[dict]) -> dict:
    """Analyze visual patterns from image search results using GPT-4."""
    # If we have downloaded images, analyze them with Vision
    local_images = [img for img in images_data if img.get("local_path")]

    if local_images:
        return _analyze_with_vision(local_images)

    # Otherwise analyze metadata
    prompt = f"""Based on these {len(images_data)} recruitment ad image search results,
analyze the visual patterns commonly used in effective recruitment advertising.

IMAGE METADATA:
{json.dumps(images_data[:20], indent=2)}

Return a JSON object with this structure:
{{
    "color_patterns": {{
        "primary_colors": ["list of most common primary colors with hex codes"],
        "accent_colors": ["list of common accent colors"],
        "color_combinations": ["list of effective color pairings"],
        "background_styles": ["solid, gradient, image-based, etc."]
    }},
    "layout_patterns": {{
        "common_layouts": ["list of typical layout structures"],
        "image_placement": "where images/photos are typically placed",
        "text_hierarchy": "how text is organized (headline, sub, body, CTA)",
        "whitespace_usage": "how whitespace is used"
    }},
    "imagery_patterns": {{
        "photo_subjects": ["what photos are commonly used"],
        "illustration_styles": ["common illustration approaches"],
        "icon_usage": "how icons are incorporated",
        "brand_elements": "how logos/branding are positioned"
    }},
    "typography_patterns": {{
        "heading_style": "typical heading font characteristics",
        "body_style": "typical body text characteristics",
        "size_contrast": "how size hierarchy is created",
        "font_pairing_suggestions": ["recommended font combinations"]
    }},
    "recommendations": {{
        "visual_do": ["5 visual best practices"],
        "visual_avoid": ["5 visual pitfalls to avoid"]
    }}
}}"""

    response = chat_completion(prompt, system=ANALYSIS_SYSTEM_PROMPT, json_mode=True)
    return json.loads(response)


def _analyze_with_vision(local_images: list[dict]) -> dict:
    """Analyze actual downloaded images with GPT-4 Vision."""
    # Analyze up to 5 images
    analyses = []
    for img in local_images[:5]:
        try:
            result = vision_analysis(
                img["local_path"],
                "Analyze this recruitment/HR ad image. Describe: colors (hex codes), layout, typography, imagery, overall style, and what makes it effective or ineffective."
            )
            analyses.append({"image": img.get("title", ""), "analysis": result})
        except Exception as e:
            print(f"  Vision analysis failed for {img.get('local_path')}: {e}")

    # Synthesize findings
    prompt = f"""Synthesize these {len(analyses)} individual ad analyses into unified visual patterns:

{json.dumps(analyses, indent=2)}

Return a JSON object with this structure:
{{
    "color_patterns": {{
        "primary_colors": ["hex codes"],
        "accent_colors": ["hex codes"],
        "color_combinations": ["effective pairings"],
        "background_styles": ["types"]
    }},
    "layout_patterns": {{
        "common_layouts": ["structures"],
        "image_placement": "description",
        "text_hierarchy": "description",
        "whitespace_usage": "description"
    }},
    "imagery_patterns": {{
        "photo_subjects": ["subjects"],
        "illustration_styles": ["styles"],
        "icon_usage": "description",
        "brand_elements": "description"
    }},
    "typography_patterns": {{
        "heading_style": "description",
        "body_style": "description",
        "size_contrast": "description",
        "font_pairing_suggestions": ["pairs"]
    }},
    "recommendations": {{
        "visual_do": ["5 best practices"],
        "visual_avoid": ["5 things to avoid"]
    }}
}}"""

    response = chat_completion(prompt, system=ANALYSIS_SYSTEM_PROMPT, json_mode=True)
    return json.loads(response)


def main():
    parser = argparse.ArgumentParser(description="Analyze collected recruitment ads")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment")
    args = parser.parse_args()

    service = SERVICE_LINES[args.service]
    print(f"Analyzing ads for: {service['name']}")

    # Load research data
    meta_path = RESEARCH_DIR / "meta_ads.json"
    web_path = RESEARCH_DIR / "web_ads.json"

    all_ads = []
    all_images = []

    if meta_path.exists():
        meta_data = load_json(meta_path)
        all_ads.extend(meta_data.get("ads", []))
        print(f"  Loaded {len(meta_data.get('ads', []))} Meta ads")

    if web_path.exists():
        web_data = load_json(web_path)
        all_ads.extend(web_data.get("articles", []))
        all_images.extend(web_data.get("images", []))
        print(f"  Loaded {len(web_data.get('images', []))} web images, {len(web_data.get('articles', []))} articles")

    if not all_ads and not all_images:
        print("ERROR: No research data found. Run scrape_meta_ads.py and scrape_web_ads.py first.")
        sys.exit(1)

    # Analyze copy
    print("\nAnalyzing ad copy patterns...")
    copy_analysis = analyze_ad_copy(all_ads, service["name"]) if all_ads else {}

    # Analyze visuals
    print("Analyzing visual patterns...")
    visual_analysis = analyze_visual_patterns(all_images) if all_images else {}

    # Combine into final analysis
    analysis = {
        "service": args.service,
        "service_name": service["name"],
        "timestamp": timestamp(),
        "copy_analysis": copy_analysis,
        "visual_analysis": visual_analysis,
        "generation_brief": {
            "tone": service["tone"],
            "target_audience": service["target_audience"],
            "keywords": service["keywords"],
        },
    }

    output_path = RESEARCH_DIR / "analysis.json"
    save_json(analysis, output_path)
    print(f"\nAnalysis saved to {output_path}")


if __name__ == "__main__":
    main()
