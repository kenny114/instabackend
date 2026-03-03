"""
Auto-iterate on ads based on scoring feedback. Regenerates copy and images with improvements.

Usage:
    python iterate_ad.py --scores .tmp/output/scores_*.json --copy-file .tmp/output/copy_*.json

Output:
    .tmp/output/versions/  (iteration history)
    .tmp/output/final/     (improved flyers)
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    OUTPUT_DIR, FINAL_DIR, VERSIONS_DIR, RESEARCH_DIR,
    MAX_ITERATIONS, MIN_SCORE_THRESHOLD, SERVICE_LINES,
)
from utils import chat_completion, load_json, save_json, timestamp

# Import sibling tools
from generate_copy import generate_ad_copy
from generate_flyer import build_dalle_prompt, generate_dalle_image
from compose_flyer import compose_flyer
from score_ad import score_single_ad


ITERATION_SYSTEM = """You are an advertising creative director iterating on recruitment ads.
Given feedback on a previous version, generate improved copy that directly addresses every issue raised.
Keep what works, fix what doesn't. Be specific and decisive in your changes."""


def improve_copy(original_variant: dict, score_result: dict, service_key: str) -> dict:
    """Generate improved copy based on scoring feedback."""
    improvements = score_result.get("improvements_needed", [])
    iteration_prompt = score_result.get("iteration_prompt", "")
    strengths = score_result.get("top_strengths", [])

    prompt = f"""Improve this recruitment ad copy based on feedback.

ORIGINAL COPY:
{json.dumps(original_variant, indent=2)}

SCORES:
{json.dumps(score_result.get('scores', {}), indent=2)}

STRENGTHS TO KEEP:
{json.dumps(strengths)}

IMPROVEMENTS NEEDED:
{json.dumps(improvements, indent=2)}

ITERATION DIRECTION:
{iteration_prompt}

SERVICE: {SERVICE_LINES[service_key]['name']}
TONE: {SERVICE_LINES[service_key]['tone']}

Return improved copy as a JSON object with the same structure:
{{
    "variant_number": {original_variant.get('variant_number', 1)},
    "angle": "{original_variant.get('angle', 'improved')}",
    "headline": "...",
    "subheadline": "...",
    "body": "...",
    "bullet_points": ["...", "...", "..."],
    "cta": "...",
    "tagline": "..."
}}

Keep the same angle but address every piece of feedback. Make the copy sharper, not longer."""

    response = chat_completion(prompt, system=ITERATION_SYSTEM, json_mode=True)
    return json.loads(response)


def run_iteration_cycle(
    score_path: str,
    copy_path: str,
    service_key: str = "recruitment",
    max_iterations: int = None,
) -> dict:
    """Run the full iteration cycle: score → improve copy → regenerate → re-score."""
    max_iter = max_iterations or MAX_ITERATIONS
    scores_data = load_json(score_path)
    copy_data = load_json(copy_path)
    variants = copy_data.get("variants", [])

    # Load research for scoring context
    analysis_path = RESEARCH_DIR / "analysis.json"
    research = load_json(analysis_path) if analysis_path.exists() else None
    visual_analysis = research.get("visual_analysis") if research else None

    iteration_history = []

    for score_entry in scores_data.get("scores", []):
        if score_entry.get("passed_threshold"):
            print(f"  {Path(score_entry['image_path']).name}: Already passed — skipping")
            continue

        if score_entry.get("error"):
            continue

        image_path = score_entry["image_path"]
        avg_score = score_entry.get("average_score", 0)
        print(f"\nIterating on: {Path(image_path).name} (score: {avg_score})")

        # Find the matching copy variant
        # Try to match by variant number from the filename
        current_variant = variants[0] if variants else {}
        current_score = score_entry
        current_image = image_path

        for iteration in range(1, max_iter + 1):
            ts = timestamp()
            print(f"\n  --- Iteration {iteration}/{max_iter} ---")

            # Archive current version
            version_dir = VERSIONS_DIR / f"iter_{iteration}_{ts}"
            version_dir.mkdir(parents=True, exist_ok=True)
            if Path(current_image).exists():
                shutil.copy2(current_image, version_dir / Path(current_image).name)
            save_json(current_score, version_dir / "score.json")
            save_json(current_variant, version_dir / "copy.json")

            # Step 1: Improve copy
            print("  Improving copy...")
            improved_variant = improve_copy(current_variant, current_score, service_key)
            print(f"    New headline: {improved_variant.get('headline', '')}")

            # Step 2: Regenerate image
            print("  Generating new background...")
            try:
                dalle_prompt = build_dalle_prompt(
                    service_key=service_key,
                    ad_size_name="instagram_square",
                    copy_variant=improved_variant,
                    visual_analysis=visual_analysis,
                )
                image_url = generate_dalle_image(dalle_prompt, size="1024x1024")
                from utils import download_image
                bg_path = OUTPUT_DIR / f"dalle_iter{iteration}_{ts}.png"
                download_image(image_url, bg_path)
            except Exception as e:
                print(f"    Image generation failed: {e}, reusing previous background")
                bg_path = Path(current_image)

            # Step 3: Compose new flyer
            print("  Composing flyer...")
            new_flyer_path = FINAL_DIR / f"flyer_iter{iteration}_{ts}.png"
            compose_flyer(
                background_path=str(bg_path),
                copy_variant=improved_variant,
                output_path=str(new_flyer_path),
            )

            # Step 4: Re-score
            print("  Scoring new version...")
            try:
                new_score = score_single_ad(str(new_flyer_path), research_context=research)
                new_avg = new_score.get("average_score", 0)
                print(f"    Score: {avg_score} → {new_avg}")

                iteration_history.append({
                    "iteration": iteration,
                    "previous_score": avg_score,
                    "new_score": new_avg,
                    "image": str(new_flyer_path),
                    "improvements_applied": current_score.get("improvements_needed", []),
                })

                # Check if we've passed the threshold
                if new_avg >= MIN_SCORE_THRESHOLD:
                    print(f"    PASSED threshold ({MIN_SCORE_THRESHOLD}) — stopping iteration")
                    break

                # Check if score is declining
                if new_avg < avg_score - 0.5:
                    print(f"    Score declining — reverting to previous version")
                    break

                # Update for next iteration
                current_variant = improved_variant
                current_score = new_score
                current_image = str(new_flyer_path)
                avg_score = new_avg

            except Exception as e:
                print(f"    Scoring failed: {e}")
                break

    return {
        "total_iterations": len(iteration_history),
        "history": iteration_history,
    }


def main():
    parser = argparse.ArgumentParser(description="Iterate on ads based on scoring feedback")
    parser.add_argument("--scores", type=str, required=True, help="Path to scores JSON")
    parser.add_argument("--copy-file", type=str, required=True, help="Path to copy JSON")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    args = parser.parse_args()

    print(f"Starting iteration cycle (max {args.max_iterations} iterations)")
    print(f"Score threshold: {MIN_SCORE_THRESHOLD}/10\n")

    result = run_iteration_cycle(
        score_path=args.scores,
        copy_path=args.copy_file,
        service_key=args.service,
        max_iterations=args.max_iterations,
    )

    # Save iteration summary
    ts = timestamp()
    save_json(result, OUTPUT_DIR / f"iteration_summary_{ts}.json")
    print(f"\nIteration complete. {result['total_iterations']} iteration(s) performed.")
    print(f"Summary saved to {OUTPUT_DIR / f'iteration_summary_{ts}.json'}")


if __name__ == "__main__":
    main()
