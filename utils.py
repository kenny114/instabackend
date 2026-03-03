"""
Shared utilities for the recruitment ad/flyer pipeline.
API clients, file I/O, and image processing helpers.
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, PROJECT_ROOT


# ── API Clients ────────────────────────────────────────────────────────

def get_openai_client():
    """Return an initialized OpenAI client."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env")
    return OpenAI(api_key=OPENAI_API_KEY)


def chat_completion(prompt: str, system: str = "", model: str = None, json_mode: bool = False) -> str:
    """Send a chat completion request to OpenAI and return the response text."""
    client = get_openai_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {"model": model or OPENAI_MODEL, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def vision_analysis(image_path: str, prompt: str, model: str = None) -> str:
    """Analyze an image using GPT-4 Vision."""
    import base64
    client = get_openai_client()

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    response = client.chat.completions.create(
        model=model or OPENAI_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
    )
    return response.choices[0].message.content


# ── HTTP Helpers ───────────────────────────────────────────────────────

def fetch_json(url: str, params: dict = None, headers: dict = None, retries: int = 3) -> dict:
    """GET request with retries. Returns parsed JSON."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def download_image(url: str, save_path: Path) -> Path:
    """Download an image from a URL and save it locally."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)
    return save_path


# ── File I/O ───────────────────────────────────────────────────────────

def save_json(data: dict | list, path: Path):
    """Save data as formatted JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> dict | list:
    """Load JSON from a file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def timestamp() -> str:
    """Return a timestamp string for versioning."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Image Helpers ──────────────────────────────────────────────────────

def resize_image(input_path: Path, output_path: Path, size: tuple[int, int]):
    """Resize an image to the given (width, height)."""
    from PIL import Image
    img = Image.open(input_path)
    img = img.resize(size, Image.LANCZOS)
    img.save(output_path, quality=95)
    return output_path


def add_text_overlay(
    image_path: Path,
    output_path: Path,
    text: str,
    position: tuple[int, int] = (50, 50),
    font_size: int = 48,
    color: str = "#FFFFFF",
    font_name: str = "arial.ttf",
):
    """Add text overlay to an image using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype(font_name, font_size)
    except OSError:
        font = ImageFont.load_default()

    # Convert hex color to RGB
    hex_color = color.lstrip("#")
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    draw.text(position, text, fill=(*rgb, 255), font=font)
    result = Image.alpha_composite(img, overlay)
    result.convert("RGB").save(output_path, quality=95)
    return output_path
