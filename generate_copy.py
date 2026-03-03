"""
Generate ad/flyer copy for recruitment services using GPT-4.

Usage:
    python generate_copy.py --service recruitment --type flyer
    python generate_copy.py --service learning_development --type social_ad

Input:
    .tmp/research/analysis.json (optional — uses research insights if available)

Output:
    .tmp/output/copy_{service}_{type}_{timestamp}.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RESEARCH_DIR, OUTPUT_DIR, SERVICE_LINES
from utils import chat_completion, save_json, timestamp


COPYWRITER_SYSTEM = """You are an elite advertising copywriter specializing in B2B recruitment and HR services.
You write copy that is professional yet compelling, avoiding generic corporate speak.
Every word earns its place. Headlines stop the scroll. CTAs drive action.
You understand the recruitment industry deeply — the pain of bad hires, the value of great talent,
and the impact of professional development on business outcomes."""


def generate_ad_copy(
    service_key: str,
    ad_type: str = "flyer",
    research_context: dict = None,
    custom_brief: str = "",
    num_variants: int = 3,
) -> dict:
    """Generate multiple copy variants for an ad or flyer."""
    service = SERVICE_LINES[service_key]

    # Build context from research if available
    research_section = ""
    if research_context:
        copy_analysis = research_context.get("copy_analysis", {})
        if copy_analysis:
            headline_patterns = copy_analysis.get("headline_patterns", {})
            body_patterns = copy_analysis.get("body_copy_patterns", {})
            messaging = copy_analysis.get("messaging_strategy", {})
            research_section = f"""
RESEARCH INSIGHTS (use these to inform your copy):
- Best headline structures: {json.dumps(headline_patterns.get('common_structures', []))}
- Power words: {json.dumps(headline_patterns.get('power_words', []))}
- Effective CTAs: {json.dumps(body_patterns.get('cta_phrases', []))}
- Value propositions that work: {json.dumps(messaging.get('value_propositions', []))}
- Pain points to address: {json.dumps(messaging.get('pain_points_addressed', []))}
- Emotional triggers: {json.dumps(messaging.get('emotional_triggers', []))}
"""

    ad_type_specs = {
        "flyer": {
            "description": "A4 printed flyer or digital flyer",
            "constraints": "Headline (max 8 words), subheadline (max 15 words), body (max 50 words), 3 bullet points, CTA (max 5 words), tagline (max 8 words)",
        },
        "social_ad": {
            "description": "Social media ad (Instagram/Facebook/LinkedIn)",
            "constraints": "Headline (max 6 words), body (max 30 words), CTA (max 4 words), hashtags (5 relevant)",
        },
        "story_ad": {
            "description": "Instagram/Facebook Story ad",
            "constraints": "Headline (max 5 words), body (max 15 words), CTA (max 3 words)",
        },
        "linkedin_ad": {
            "description": "LinkedIn sponsored content",
            "constraints": "Headline (max 10 words), intro text (max 60 words), CTA (max 4 words)",
        },
    }

    spec = ad_type_specs.get(ad_type, ad_type_specs["flyer"])

    prompt = f"""Create {num_variants} distinct copy variants for a {spec['description']} advertising {service['name']} services.

SERVICE DETAILS:
- Service: {service['name']}
- Tone: {service['tone']}
- Target audience: {service['target_audience']}
- Key terms: {', '.join(service['keywords'])}
{research_section}
{f"ADDITIONAL BRIEF: {custom_brief}" if custom_brief else ""}

COPY CONSTRAINTS:
{spec['constraints']}

Each variant should take a different angle:
- Variant 1: Pain-point focused (highlight what they're struggling with)
- Variant 2: Aspiration-focused (highlight the transformation/outcome)
- Variant 3: Authority-focused (highlight expertise and track record)

Return a JSON object:
{{
    "variants": [
        {{
            "variant_number": 1,
            "angle": "pain-point",
            "headline": "...",
            "subheadline": "...",
            "body": "...",
            "bullet_points": ["...", "...", "..."],
            "cta": "...",
            "tagline": "...",
            "hashtags": ["...", "..."]
        }}
    ]
}}

Only include fields that are relevant to the ad type. Omit any field not in the constraints."""

    response = chat_completion(prompt, system=COPYWRITER_SYSTEM, json_mode=True)
    return json.loads(response)


def main():
    parser = argparse.ArgumentParser(description="Generate ad/flyer copy")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment")
    parser.add_argument("--type", choices=["flyer", "social_ad", "story_ad", "linkedin_ad"],
                        default="flyer", dest="ad_type")
    parser.add_argument("--brief", type=str, default="", help="Additional creative brief")
    parser.add_argument("--variants", type=int, default=3, help="Number of copy variants")
    args = parser.parse_args()

    service = SERVICE_LINES[args.service]
    print(f"Generating {args.ad_type} copy for: {service['name']}")

    # Load research analysis if available
    analysis_path = RESEARCH_DIR / "analysis.json"
    research = None
    if analysis_path.exists():
        research = json.loads(analysis_path.read_text(encoding="utf-8"))
        print("  Using research insights for context")

    # Generate copy
    print(f"  Generating {args.variants} copy variants...")
    copy_data = generate_ad_copy(
        service_key=args.service,
        ad_type=args.ad_type,
        research_context=research,
        custom_brief=args.brief,
        num_variants=args.variants,
    )

    # Save output
    ts = timestamp()
    output = {
        "service": args.service,
        "ad_type": args.ad_type,
        "timestamp": ts,
        "used_research": research is not None,
        **copy_data,
    }

    output_path = OUTPUT_DIR / f"copy_{args.service}_{args.ad_type}_{ts}.json"
    save_json(output, output_path)
    print(f"\nSaved {len(copy_data.get('variants', []))} variants to {output_path}")

    # Print preview
    for v in copy_data.get("variants", []):
        print(f"\n--- Variant {v.get('variant_number')} ({v.get('angle')}) ---")
        print(f"  Headline: {v.get('headline', '')}")
        if v.get("subheadline"):
            print(f"  Sub: {v.get('subheadline')}")
        print(f"  CTA: {v.get('cta', '')}")


if __name__ == "__main__":
    main()
