"""
Configuration for the recruitment ad/flyer pipeline.
Ad sizes, brand defaults, prompt templates, and shared constants.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
TMP_DIR = PROJECT_ROOT / ".tmp"
RESEARCH_DIR = TMP_DIR / "research"
OUTPUT_DIR = TMP_DIR / "output"
FINAL_DIR = OUTPUT_DIR / "final"
VERSIONS_DIR = OUTPUT_DIR / "versions"

# Ensure directories exist
for d in [RESEARCH_DIR, OUTPUT_DIR, FINAL_DIR, VERSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API Keys (loaded from .env) ───────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "curious_coder~facebook-ads-library-scraper")

# ── Ad Sizes (width x height in pixels) ───────────────────────────────
AD_SIZES = {
    "instagram_square": (1080, 1080),
    "instagram_story": (1080, 1920),
    "facebook_feed": (1200, 628),
    "facebook_story": (1080, 1920),
    "linkedin_feed": (1200, 627),
    "linkedin_story": (1080, 1920),
    "general_flyer": (2480, 3508),  # A4 at 300 DPI
}

DEFAULT_AD_SIZES = ["instagram_square", "facebook_feed", "linkedin_feed"]

# ── Brand Defaults ─────────────────────────────────────────────────────
BRAND = {
    "primary_color": "#1A365D",      # Deep navy
    "secondary_color": "#E53E3E",    # Accent red
    "accent_color": "#38A169",       # Success green
    "background_color": "#FFFFFF",
    "text_color": "#1A202C",
    "font_heading": "Arial Bold",
    "font_body": "Arial",
    "logo_path": None,  # Set to path if brand logo exists
}

# ── Service Lines ──────────────────────────────────────────────────────
SERVICE_LINES = {
    "recruitment": {
        "name": "Recruitment",
        "keywords": ["hiring", "talent acquisition", "recruitment", "staffing", "job openings", "career opportunities"],
        "tone": "professional, confident, action-oriented",
        "target_audience": "HR managers, business owners, job seekers",
    },
    "performance_management": {
        "name": "Performance Management",
        "keywords": ["performance review", "employee evaluation", "KPIs", "goal setting", "productivity"],
        "tone": "authoritative, results-focused, supportive",
        "target_audience": "HR directors, team leads, C-suite executives",
    },
    "learning_development": {
        "name": "Learning & Development",
        "keywords": ["training", "upskilling", "professional development", "workshops", "corporate training"],
        "tone": "inspiring, growth-minded, empowering",
        "target_audience": "L&D managers, HR teams, employees seeking growth",
    },
}

# ── Research Settings ──────────────────────────────────────────────────
META_AD_LIBRARY_BASE_URL = "https://graph.facebook.com/v25.0/ads_archive"
GOOGLE_SEARCH_BASE_URL = "https://www.googleapis.com/customsearch/v1"

RESEARCH_SEARCH_TERMS = [
    "recruitment agency flyer",
    "hiring ad design",
    "HR services advertisement",
    "staffing company social media ad",
    "corporate training flyer design",
    "performance management ad",
    "talent acquisition social post",
]

MAX_RESEARCH_RESULTS = 10

# ── Generation Settings ────────────────────────────────────────────────
OPENAI_MODEL = "gpt-4o"
DALLE_MODEL = "dall-e-3"
DALLE_QUALITY = "hd"
DALLE_SIZE_MAP = {
    "instagram_square": "1024x1024",
    "facebook_feed": "1792x1024",
    "linkedin_feed": "1792x1024",
    "instagram_story": "1024x1792",
    "facebook_story": "1024x1792",
    "linkedin_story": "1024x1792",
    "general_flyer": "1024x1792",
}

# ── Iteration Settings ─────────────────────────────────────────────────
MAX_ITERATIONS = 3
MIN_SCORE_THRESHOLD = 7.5  # Out of 10 — stop iterating once this is reached
SCORING_CRITERIA = [
    "visual_appeal",
    "copy_clarity",
    "cta_strength",
    "brand_alignment",
    "target_audience_fit",
    "overall_effectiveness",
]
