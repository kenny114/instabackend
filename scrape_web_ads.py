"""
Scrape recruitment ad/flyer examples from the web using Google Custom Search.

Usage:
    python scrape_web_ads.py [--service recruitment|performance_management|learning_development]

Output:
    .tmp/research/web_ads.json
    .tmp/research/images/  (downloaded reference images)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    GOOGLE_API_KEY, GOOGLE_CSE_ID, GOOGLE_SEARCH_BASE_URL,
    RESEARCH_DIR, SERVICE_LINES, RESEARCH_SEARCH_TERMS,
)
from utils import fetch_json, download_image, save_json, timestamp


def google_image_search(query: str, num_results: int = 10) -> list[dict]:
    """Search Google Custom Search API for images."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("WARNING: GOOGLE_API_KEY or GOOGLE_CSE_ID not set. Using mock data.")
        return _mock_web_results(query)

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "searchType": "image",
        "num": min(num_results, 10),
        "imgSize": "large",
        "safe": "active",
    }

    try:
        data = fetch_json(GOOGLE_SEARCH_BASE_URL, params=params)
        if "error" in data:
            print(f"  Google API error for '{query}': {data['error'].get('message', data['error'])}")
            return []
        items = data.get("items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("title", ""),
                "image_url": item.get("link", ""),
                "thumbnail_url": item.get("image", {}).get("thumbnailLink", ""),
                "source_url": item.get("image", {}).get("contextLink", ""),
                "width": item.get("image", {}).get("width"),
                "height": item.get("image", {}).get("height"),
            })
        if not results:
            print(f"  WARNING: Google returned no results for '{query}'.")
        return results
    except Exception as e:
        print(f"  Error searching '{query}': {e}")
        return []


def google_text_search(query: str, num_results: int = 10) -> list[dict]:
    """Search Google Custom Search for text results (ad copy, articles)."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("WARNING: GOOGLE_API_KEY or GOOGLE_CSE_ID not set for text search.")
        return []

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num_results, 10),
    }

    try:
        data = fetch_json(GOOGLE_SEARCH_BASE_URL, params=params)
        items = data.get("items", [])
        return [{
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
        } for item in items]
    except Exception as e:
        print(f"  Error searching '{query}': {e}")
        return []


def download_reference_images(image_results: list[dict], max_downloads: int = 20) -> list[dict]:
    """Download reference images for analysis."""
    images_dir = RESEARCH_DIR / "images"
    images_dir.mkdir(exist_ok=True)

    downloaded = []
    for i, result in enumerate(image_results[:max_downloads]):
        url = result.get("image_url", "")
        if not url:
            continue
        try:
            ext = Path(url.split("?")[0]).suffix or ".jpg"
            save_path = images_dir / f"ref_{i:03d}{ext}"
            download_image(url, save_path)
            result["local_path"] = str(save_path)
            downloaded.append(result)
            print(f"  Downloaded {i+1}/{max_downloads}: {save_path.name}")
        except Exception as e:
            print(f"  Failed to download image {i}: {e}")

    return downloaded


def _mock_web_results(query: str) -> list[dict]:
    """Mock image search results for development."""
    return [{
        "title": f"Sample recruitment flyer - {query}",
        "image_url": "",
        "thumbnail_url": "",
        "source_url": "https://example.com",
        "width": 1080,
        "height": 1080,
    }]


def _mock_text_results(query: str) -> list[dict]:
    """Mock text search results for development."""
    return [{
        "title": f"Top Recruitment Ad Examples - {query}",
        "snippet": "Discover the best recruitment advertising strategies. Use bold headlines, clear CTAs, and professional imagery to attract top talent.",
        "url": "https://example.com",
    }]


def main():
    parser = argparse.ArgumentParser(description="Scrape web for recruitment ad examples")
    parser.add_argument("--service", choices=SERVICE_LINES.keys(), default="recruitment",
                        help="Service line to research")
    parser.add_argument("--download-images", action="store_true",
                        help="Download reference images locally")
    args = parser.parse_args()

    service = SERVICE_LINES[args.service]

    # Build search queries combining service keywords with ad-related terms
    queries = [f"{kw} flyer design" for kw in service["keywords"][:3]]
    queries += [f"{kw} social media ad" for kw in service["keywords"][:3]]
    queries += RESEARCH_SEARCH_TERMS[:3]

    print(f"Researching web ads for: {service['name']}")
    print(f"Running {len(queries)} searches...")

    all_images = []
    all_text = []

    for query in queries:
        print(f"\n  Searching: '{query}'")
        images = google_image_search(query, num_results=10)
        text = google_text_search(f"{query} examples best practices", num_results=5)
        all_images.extend(images)
        all_text.extend(text)
        print(f"    Found {len(images)} images, {len(text)} articles")

    # Deduplicate by URL
    seen_urls = set()
    unique_images = []
    for img in all_images:
        url = img.get("image_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_images.append(img)

    if args.download_images:
        print(f"\nDownloading up to 20 reference images...")
        unique_images = download_reference_images(unique_images, max_downloads=20)

    output = {
        "service": args.service,
        "timestamp": timestamp(),
        "total_images": len(unique_images),
        "total_articles": len(all_text),
        "images": unique_images,
        "articles": all_text,
    }

    output_path = RESEARCH_DIR / "web_ads.json"
    save_json(output, output_path)
    print(f"\nSaved {len(unique_images)} images and {len(all_text)} articles to {output_path}")


if __name__ == "__main__":
    main()
