"""
SQLite persistence layer for scraped ads.

Stores all scraped ads permanently in data/ads.db, deduplicated by ad_id.
Scripts read from here instead of re-scraping.

Usage:
    from db import upsert_ads, get_ads, get_ad_count

    upsert_ads(ads_list, service="recruitment")
    ads = get_ads(service="recruitment", limit=100)
    count = get_ad_count(service="recruitment")
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "ads.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id       TEXT    UNIQUE,
                source      TEXT,
                service     TEXT,
                search_term TEXT,
                page_name   TEXT,
                body        TEXT,
                title       TEXT,
                description TEXT,
                snapshot_url TEXT,
                platforms   TEXT,
                scraped_at  TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_service ON ads(service)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_source  ON ads(source)")
        conn.commit()


def upsert_ads(ads: list[dict], service: str):
    """Insert ads, skipping duplicates by ad_id. Returns count of new rows inserted."""
    init_db()
    inserted = 0
    with _connect() as conn:
        for ad in ads:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ads
                        (ad_id, source, service, search_term, page_name,
                         body, title, description, snapshot_url, platforms, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        ad.get("ad_id"),
                        ad.get("source", "unknown"),
                        service,
                        ad.get("search_term", ""),
                        ad.get("page_name", ""),
                        next(iter(ad.get("bodies") or []), ""),
                        next(iter(ad.get("titles") or []), ""),
                        next(iter(ad.get("descriptions") or []), ""),
                        ad.get("snapshot_url", ""),
                        json.dumps(ad.get("platforms") or []),
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception:
                pass
        conn.commit()
    return inserted


def get_ads(service: str = None, limit: int = None) -> list[dict]:
    """Fetch ads from DB, optionally filtered by service."""
    init_db()
    with _connect() as conn:
        if service:
            query = "SELECT * FROM ads WHERE service = ? ORDER BY id DESC"
            params = (service,)
        else:
            query = "SELECT * FROM ads ORDER BY id DESC"
            params = ()
        if limit:
            query += f" LIMIT {int(limit)}"
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "source": r["source"],
            "service": r["service"],
            "search_term": r["search_term"],
            "ad_id": r["ad_id"],
            "page_name": r["page_name"],
            "bodies": [r["body"]] if r["body"] else [],
            "titles": [r["title"]] if r["title"] else [],
            "descriptions": [r["description"]] if r["description"] else [],
            "snapshot_url": r["snapshot_url"],
            "platforms": json.loads(r["platforms"] or "[]"),
        }
        for r in rows
    ]


def get_ad_count(service: str = None) -> int:
    """Return total number of stored ads, optionally filtered by service."""
    init_db()
    with _connect() as conn:
        if service:
            return conn.execute(
                "SELECT COUNT(*) FROM ads WHERE service = ?", (service,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
