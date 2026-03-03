"""
FastAPI backend for the ad generator pipeline.
Exposes each Python tool as an HTTP endpoint.
"""

import io
import base64
import subprocess
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Ad Generator Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ────────────────────────────────────────────────────

class ServiceRequest(BaseModel):
    service: str = "recruitment"

class WebAdsRequest(BaseModel):
    service: str = "recruitment"
    download_images: bool = False

class GenerateCopyRequest(BaseModel):
    service: str = "recruitment"
    ad_type: str = "flyer"
    brief: Optional[str] = None
    variants: Optional[int] = None

class GenerateFlyerRequest(BaseModel):
    service: str = "recruitment"
    copy_file: Optional[str] = None
    sizes: Optional[list[str]] = None

class ComposeFlyerRequest(BaseModel):
    manifest: str
    copy_file: str
    variant: Optional[int] = None

class ScoreAdRequest(BaseModel):
    image_path: Optional[str] = None
    manifest_path: Optional[str] = None

class FullPipelineRequest(BaseModel):
    service: str = "recruitment"
    ad_type: str = "flyer"


# ── Tool Runner ───────────────────────────────────────────────────────

def run_tool(script: str, args: list[str], timeout: int = 120) -> dict:
    """Run a Python tool script and capture output."""
    script_path = Path(__file__).parent / script
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent),
        )
        output = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            return {
                "status": "error",
                "output": f"{output}\n{stderr}".strip() or "Tool failed with no output",
            }
        return {
            "status": "success",
            "output": output or "Completed successfully.",
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": f"Tool timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "output": f"Error: {e}"}


def extract_images(output: str) -> list[str]:
    """Extract image file paths from tool output and convert to base64."""
    import json as json_mod
    import re
    from config import FINAL_DIR, OUTPUT_DIR

    images = []

    # Try manifest from output
    manifest_match = re.search(r"Manifest:\s*(.+\.json)", output)
    if manifest_match:
        try:
            manifest = json_mod.loads(Path(manifest_match.group(1).strip()).read_text())
            for f in manifest.get("flyers", []):
                if f.get("file") and Path(f["file"]).exists():
                    images.append(f["file"])
            for img in manifest.get("images", []):
                if img.get("file") and Path(img["file"]).exists():
                    images.append(img["file"])
        except Exception:
            pass

    # Try "Composed N final flyers in <dir>" pattern
    composed_match = re.search(r"Composed \d+ final flyers in (.+)", output)
    if composed_match and not images:
        try:
            dir_path = Path(composed_match.group(1).strip())
            files = list(dir_path.iterdir())
            manifests = sorted(
                [f for f in files if f.name.startswith("compose_manifest_") and f.suffix == ".json"]
            )
            if manifests:
                manifest = json_mod.loads(manifests[-1].read_text())
                for f in manifest.get("flyers", []):
                    if f.get("file") and Path(f["file"]).exists():
                        images.append(f["file"])
        except Exception:
            pass

    return images


def images_to_base64(image_paths: list[str]) -> list[dict]:
    """Convert image file paths to base64 data URLs."""
    results = []
    for img_path in image_paths:
        try:
            p = Path(img_path)
            if not p.exists():
                continue
            data = p.read_bytes()
            ext = p.suffix.lower()
            mime = {"png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")
            b64 = base64.b64encode(data).decode()
            results.append({
                "filename": p.name,
                "data_url": f"data:{mime};base64,{b64}",
            })
        except Exception:
            pass
    return results


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tools/research_meta_ads")
def research_meta_ads(req: ServiceRequest):
    result = run_tool("scrape_meta_ads.py", ["--service", req.service], timeout=700)
    return result


@app.post("/tools/research_web_ads")
def research_web_ads(req: WebAdsRequest):
    args = ["--service", req.service]
    if req.download_images:
        args.append("--download-images")
    result = run_tool("scrape_web_ads.py", args)
    return result


@app.post("/tools/analyze_ads")
def analyze_ads(req: ServiceRequest):
    result = run_tool("analyze_ads.py", ["--service", req.service])
    return result


@app.post("/tools/generate_copy")
def generate_copy(req: GenerateCopyRequest):
    args = ["--service", req.service, "--type", req.ad_type]
    if req.brief:
        args.extend(["--brief", req.brief])
    if req.variants:
        args.extend(["--variants", str(req.variants)])
    result = run_tool("generate_copy.py", args)
    return result


@app.post("/tools/generate_flyer_image")
def generate_flyer_image(req: GenerateFlyerRequest):
    args = ["--service", req.service]
    if req.copy_file:
        args.extend(["--copy-file", req.copy_file])
    if req.sizes:
        args.extend(["--size"] + req.sizes)
    result = run_tool("generate_flyer.py", args, timeout=180)
    if result["status"] == "success":
        image_paths = extract_images(result["output"])
        if image_paths:
            result["images"] = images_to_base64(image_paths)
    return result


@app.post("/tools/compose_flyer")
def compose_flyer_endpoint(req: ComposeFlyerRequest):
    args = ["--manifest", req.manifest, "--copy-file", req.copy_file]
    if req.variant:
        args.extend(["--variant", str(req.variant)])
    result = run_tool("compose_flyer.py", args)
    if result["status"] == "success":
        image_paths = extract_images(result["output"])
        if image_paths:
            result["images"] = images_to_base64(image_paths)
    return result


@app.post("/tools/score_ad")
def score_ad(req: ScoreAdRequest):
    args = []
    if req.image_path:
        args.extend(["--image", req.image_path])
    elif req.manifest_path:
        args.extend(["--manifest", req.manifest_path])
    result = run_tool("score_ad.py", args)
    return result


@app.post("/tools/run_full_pipeline")
def run_full_pipeline(req: FullPipelineRequest):
    """Run the complete pipeline by calling each tool in sequence."""
    results = []

    # Step 1: Research
    meta = run_tool("scrape_meta_ads.py", ["--service", req.service], timeout=700)
    results.append(f"[Research Meta] {meta['output'].split(chr(10))[-1]}")

    web = run_tool("scrape_web_ads.py", ["--service", req.service])
    results.append(f"[Research Web] {web['output'].split(chr(10))[-1]}")

    # Step 2: Analyze
    analysis = run_tool("analyze_ads.py", ["--service", req.service])
    results.append(f"[Analysis] {analysis['output'].split(chr(10))[-1]}")

    # Step 3: Generate copy
    copy = run_tool("generate_copy.py", ["--service", req.service, "--type", req.ad_type])
    results.append(f"[Copy] {copy['output'].split(chr(10))[-1]}")

    # Extract copy file path
    import re
    copy_match = re.search(r"Saved \d+ variants to (.+\.json)", copy["output"])
    if not copy_match:
        results.append("[Error] Could not determine copy file path. Stopping pipeline.")
        return {"status": "error", "output": "\n".join(results)}

    copy_file_path = copy_match.group(1).strip()

    # Step 4: Generate DALL-E images
    flyer = run_tool("generate_flyer.py", ["--service", req.service, "--copy-file", copy_file_path], timeout=180)
    results.append(f"[DALL-E] {flyer['output'].split(chr(10))[-1]}")

    manifest_match = re.search(r"Manifest:\s*(.+\.json)", flyer["output"])
    if not manifest_match or flyer["status"] == "error":
        results.append("[Error] Image generation failed or manifest not found.")
        return {"status": "error", "output": "\n".join(results)}

    manifest_path = manifest_match.group(1).strip()

    # Step 5: Compose final flyers
    compose = run_tool("compose_flyer.py", ["--manifest", manifest_path, "--copy-file", copy_file_path])
    results.append(f"[Compose] {compose['output'].split(chr(10))[-1]}")

    if compose["status"] == "error":
        results.append("[Error] Flyer composition failed.")
        return {"status": "error", "output": "\n".join(results)}

    results.append("[Done] Full pipeline complete.")

    response = {"status": "success", "output": "\n".join(results)}

    image_paths = extract_images(compose["output"])
    if image_paths:
        response["images"] = images_to_base64(image_paths)

    return response


@app.get("/images/{filepath:path}")
def serve_image(filepath: str):
    """Serve generated images from .tmp/output/."""
    from config import OUTPUT_DIR
    resolved = (OUTPUT_DIR / filepath).resolve()
    if not str(resolved).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Not found")

    ext = resolved.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "application/octet-stream")
    return Response(content=resolved.read_bytes(), media_type=mime)
