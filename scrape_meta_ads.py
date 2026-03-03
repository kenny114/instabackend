"""
Scrape recruitment-related ads from the Meta Ad Library API.

Usage:
    python scrape_meta_ads.py [--service recruitment|performance_management|learning_development]

Output:
    .tmp/research/meta_ads.json
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    META_ACCESS_TOKEN, META_AD_LIBRARY_BASE_URL,
    RESEARCH_DIR, SERVICE_LINES, MAX_RESEARCH_RESULTS,
)
from utils import fetch_json, save_json, download_image, timestamp


def search_meta_ads(search_terms: list[str], limit: int = 25) -> list[dict]:
    """Query the Meta Ad Library for ads matching search terms."""
    if not META_ACCESS_TOKEN:
        print("WARNING: META_ACCESS_TOKEN not set. Using mock data for development.")
        return _mock_meta_results(search_terms)

    all_ads = []
    for term in search_terms:
        params = {
            "access_token": META_ACCESS_TOKEN,
            "search_terms": term,
            "ad_type": "ALL",
            "ad_reached_countries": ["US", "GB", "AU", "CA"],
            "fields": "id,ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,ad_snapshot_url,page_name,publisher_platforms,estimated_audience_size",
            "limit": min(limit, 50),
        }

        try:
            data = fetch_json(META_AD_LIBRARY_BASE_URL, params=params)
            ads = data.get("data", [])
            for ad in ads:
                all_ads.append({
                    "source": "meta_ad_library",
                    "search_term": term,
                    "ad_id": ad.get("id"),
                    "page_name": ad.get("page_name"),
                    "bodies": ad.get("ad_creative_bodies", []),
                    "titles": ad.get("ad_creative_link_titles", []),
                    "descriptions": ad.get("ad_creative_link_descriptions", []),
                    "snapshot_url": ad.get("ad_snapshot_url"),
                    "platforms": ad.get("publisher_platforms", []),
                    "audience_size": ad.get("estimated_audience_size", {}),
                })
            print(f"  Found {len(ads)} ads for '{term}'")
        except Exception as e:
            print(f"  Error searching '{term}': {e}")

    return all_ads


def _mock_meta_results(search_terms: list[str]) -> list[dict]:
    """Generate mock results for development/testing without API access."""
    mock_ads = []
    for i, term in enumerate(search_terms[:3]):
        mock_ads.append({
            "source": "meta_ad_library",
            "search_term": term,
            "ad_id": f"mock_{i}",
            "page_name": f"Sample Recruitment Agency {i+1}",
            "bodies": [f"We're hiring! Top talent meets top opportunities. {term}. Apply now and take your career to the next level."],
            "titles": [f"Join Our Team — {term.title()}"],
            "descriptions": ["Leading recruitment agency helping businesses find the best talent."],
            "snapshot_url": None,
            "platforms": ["facebook", "instagram"],
            "audience_size": {"lower_bound": 10000, "upper_bound": 50000},
        })
    return mock_ads


def main():
    parser = argparse.ArgumentParser(description="Scrape Meta Ad Library for recruitment ads")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment",
                        help="Service line to research")
    args = parser.parse_args()

    service = SERVICE_LINES[args.service]
    search_terms = service["keywords"]

    print(f"Researching Meta ads for: {service['name']}")
    print(f"Search terms: {search_terms}")

    ads = search_meta_ads(search_terms, limit=MAX_RESEARCH_RESULTS)

    output = {
        "service": args.service,
        "timestamp": timestamp(),
        "total_ads": len(ads),
        "ads": ads,
    }

    output_path = RESEARCH_DIR / "meta_ads.json"
    save_json(output, output_path)
    print(f"\nSaved {len(ads)} ads to {output_path}")


if __name__ == "__main__":
    main()
