"""
Scrape recruitment-related ads from Meta Ad Library via Apify.
Uses curious_coder/facebook-ads-library-scraper which takes Ad Library URLs.

Usage:
    python scrape_meta_ads.py [--service recruitment|performance_management|learning_development]

Output:
    .tmp/research/meta_ads.json
"""

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    APIFY_API_TOKEN, APIFY_ACTOR_ID,
    RESEARCH_DIR, SERVICE_LINES, MAX_RESEARCH_RESULTS,
)
from utils import save_json, timestamp
from db import upsert_ads, get_ad_count
import requests

APIFY_BASE = "https://api.apify.com/v2"


def _build_ad_library_url(search_term: str, country: str = "US") -> str:
    params = {
        "active_status": "all",
        "ad_type": "all",
        "country": country,
        "q": search_term,
        "search_type": "keyword_unordered",
        "media_type": "all",
    }
    return "https://www.facebook.com/ads/library/?" + urlencode(params)


def search_meta_ads(search_terms: list[str], limit: int = 25) -> list[dict]:
    """Query Meta Ad Library via Apify actor for ads matching search terms."""
    if not APIFY_API_TOKEN:
        print("ERROR: APIFY_API_TOKEN not set in .env")
        return []

    urls = [_build_ad_library_url(term) for term in search_terms]
    print(f"  Starting Apify run with {len(urls)} search URLs...")

    payload = {
        "urls": [{"url": u} for u in urls],
        "totalNumberOfRecordsRequired": min(limit * len(search_terms), 200),
    }

    # Start async run
    try:
        resp = requests.post(
            f"{APIFY_BASE}/acts/{APIFY_ACTOR_ID}/runs",
            params={"token": APIFY_API_TOKEN, "memory": 1024},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        run_data = resp.json()
        run_id = run_data["data"]["id"]
        print(f"  Run started: {run_id}")
    except Exception as e:
        print(f"  Failed to start Apify run: {e}")
        return []

    # Poll until finished
    max_wait = 600  # 10 minutes
    poll_interval = 15
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        try:
            status_resp = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_API_TOKEN},
                timeout=15,
            )
            status_resp.raise_for_status()
            status = status_resp.json()["data"]["status"]
            print(f"  [{elapsed}s] Status: {status}")
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"  Run ended with status: {status}")
                return []
        except Exception as e:
            print(f"  Polling error: {e}")

    # Fetch results
    try:
        items_resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}/dataset/items",
            params={"token": APIFY_API_TOKEN, "format": "json"},
            timeout=60,
        )
        items_resp.raise_for_status()
        items = items_resp.json()
        print(f"  Apify returned {len(items)} ads")
    except Exception as e:
        print(f"  Failed to fetch results: {e}")
        return []

    all_ads = []
    for item in items:
        snap = item.get("snapshot") or {}
        body_text = snap.get("body", {}).get("text", "") if isinstance(snap.get("body"), dict) else ""
        all_ads.append({
            "source": "meta_ad_library",
            "search_term": item.get("searchTerm") or item.get("q", ""),
            "ad_id": item.get("ad_archive_id") or item.get("adArchiveID") or item.get("id"),
            "page_name": item.get("page_name") or snap.get("page_name") or item.get("pageName", ""),
            "bodies": [body_text] if body_text else [],
            "titles": [snap["title"]] if snap.get("title") else [],
            "descriptions": [snap["link_description"]] if snap.get("link_description") else [],
            "snapshot_url": snap.get("link_url") or item.get("adSnapshotURL", ""),
            "platforms": item.get("publisher_platform") or item.get("publisherPlatform") or [],
            "audience_size": item.get("reach_estimate") or item.get("reachEstimate") or {},
        })
    return all_ads


def main():
    parser = argparse.ArgumentParser(description="Scrape Meta Ad Library via Apify")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment",
                        help="Service line to research")
    parser.add_argument("--force", action="store_true",
                        help="Force re-scrape even if DB already has data")
    args = parser.parse_args()

    service = SERVICE_LINES[args.service]

    # Skip scraping if DB already has data (unless --force)
    existing = get_ad_count(service=args.service)
    if existing > 0 and not args.force:
        print(f"Using {existing} cached ads from DB for {args.service}. Pass --force to re-scrape.")
        return

    search_terms = service["keywords"][:4]
    print(f"Researching Meta ads for: {service['name']} (via Apify)")
    print(f"Search terms: {search_terms}")

    ads = search_meta_ads(search_terms, limit=MAX_RESEARCH_RESULTS)

    # Persist to SQLite (deduplicates automatically)
    new_count = upsert_ads(ads, service=args.service)
    total_in_db = get_ad_count(service=args.service)
    print(f"\n  {new_count} new ads added to DB ({total_in_db} total for {args.service})")

    # Also write JSON for downstream compatibility
    output = {
        "service": args.service,
        "timestamp": timestamp(),
        "total_ads": len(ads),
        "ads": ads,
    }
    output_path = RESEARCH_DIR / "meta_ads.json"
    save_json(output, output_path)
    print(f"Saved {len(ads)} ads to {output_path}")


if __name__ == "__main__":
    main()
