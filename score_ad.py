"""
Score generated ads against research benchmarks using GPT-4 Vision.

Usage:
    python score_ad.py --image .tmp/output/final/flyer_v1_instagram_square_*.png
    python score_ad.py --manifest .tmp/output/final/compose_manifest_*.json

Output:
    .tmp/output/scores_{timestamp}.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RESEARCH_DIR, OUTPUT_DIR, SCORING_CRITERIA, MIN_SCORE_THRESHOLD
from utils import vision_analysis, load_json, save_json, timestamp


SCORING_SYSTEM = """You are a senior creative director at a top advertising agency, specializing in B2B recruitment marketing.
Score this ad honestly and constructively. Be specific about what works and what doesn't.
Your feedback should be actionable — not vague praise or criticism."""


def score_single_ad(image_path: str, research_context: dict = None) -> dict:
    """Score a single ad image using GPT-4 Vision."""
    research_section = ""
    if research_context:
        copy_recs = research_context.get("copy_analysis", {}).get("recommendations", {})
        visual_recs = research_context.get("visual_analysis", {}).get("recommendations", {})
        research_section = f"""
BENCHMARK (from research on top-performing recruitment ads):
Copy best practices: {json.dumps(copy_recs.get('do', []))}
Copy pitfalls: {json.dumps(copy_recs.get('avoid', []))}
Visual best practices: {json.dumps(visual_recs.get('visual_do', []))}
Visual pitfalls: {json.dumps(visual_recs.get('visual_avoid', []))}
"""

    prompt = f"""Score this recruitment/HR advertisement image on each criterion below.
For each criterion, give a score from 1-10 and specific feedback.
{research_section}

SCORING CRITERIA:
1. visual_appeal: Is the design professional, modern, and eye-catching?
2. copy_clarity: Is the text readable, clear, and compelling? (If no text visible, score layout readiness)
3. cta_strength: Is the call-to-action prominent and motivating?
4. brand_alignment: Does it feel like a premium recruitment/HR brand?
5. target_audience_fit: Would this resonate with HR managers and business owners?
6. overall_effectiveness: Would this ad stop the scroll and drive action?

Return a JSON object:
{{
    "scores": {{
        "visual_appeal": {{"score": 8, "feedback": "..."}},
        "copy_clarity": {{"score": 7, "feedback": "..."}},
        "cta_strength": {{"score": 6, "feedback": "..."}},
        "brand_alignment": {{"score": 8, "feedback": "..."}},
        "target_audience_fit": {{"score": 7, "feedback": "..."}},
        "overall_effectiveness": {{"score": 7, "feedback": "..."}}
    }},
    "average_score": 7.2,
    "top_strengths": ["strength 1", "strength 2"],
    "improvements_needed": [
        {{"issue": "specific problem", "fix": "concrete suggestion"}},
        {{"issue": "specific problem", "fix": "concrete suggestion"}},
        {{"issue": "specific problem", "fix": "concrete suggestion"}}
    ],
    "iteration_prompt": "A specific, actionable prompt for the next iteration that addresses the top improvements"
}}"""

    response = vision_analysis(image_path, prompt)

    # Parse JSON from response (handle markdown code blocks)
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser(description="Score generated ads")
    parser.add_argument("--image", type=str, help="Path to a single ad image")
    parser.add_argument("--manifest", type=str, help="Path to compose manifest JSON")
    args = parser.parse_args()

    ts = timestamp()

    # Collect images to score
    images = []
    if args.image:
        images = [{"file": args.image, "variant": "unknown", "size": "unknown"}]
    elif args.manifest:
        manifest = load_json(args.manifest)
        images = manifest.get("flyers", [])
    else:
        print("ERROR: Provide --image or --manifest")
        sys.exit(1)

    # Load research for benchmarking
    analysis_path = RESEARCH_DIR / "analysis.json"
    research = load_json(analysis_path) if analysis_path.exists() else None
    if research:
        print("Using research benchmarks for scoring")

    print(f"Scoring {len(images)} ad(s)...\n")

    all_scores = []
    for img_info in images:
        img_path = img_info["file"] if isinstance(img_info, dict) else img_info
        print(f"Scoring: {Path(img_path).name}")

        try:
            result = score_single_ad(str(img_path), research_context=research)
            avg = result.get("average_score", 0)
            passed = avg >= MIN_SCORE_THRESHOLD

            result["image_path"] = str(img_path)
            result["passed_threshold"] = passed
            all_scores.append(result)

            print(f"  Average: {avg}/10 {'PASS' if passed else 'NEEDS ITERATION'}")
            for imp in result.get("improvements_needed", [])[:2]:
                print(f"  - {imp.get('issue')}: {imp.get('fix')}")

        except Exception as e:
            print(f"  ERROR scoring: {e}")
            all_scores.append({"image_path": str(img_path), "error": str(e)})

    # Save scores
    output = {
        "timestamp": ts,
        "threshold": MIN_SCORE_THRESHOLD,
        "total_scored": len(all_scores),
        "passed": sum(1 for s in all_scores if s.get("passed_threshold")),
        "scores": all_scores,
    }

    output_path = OUTPUT_DIR / f"scores_{ts}.json"
    save_json(output, output_path)
    print(f"\nScores saved to {output_path}")
    print(f"Passed: {output['passed']}/{output['total_scored']} (threshold: {MIN_SCORE_THRESHOLD})")


if __name__ == "__main__":
    main()
