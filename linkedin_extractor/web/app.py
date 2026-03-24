"""
web/app.py — FastAPI backend serving the web UI and extraction API.
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from utils.logger import setup_logger
from utils.exceptions import CaptchaError, ProfileNotFoundError, OCRFailedError, LLMParseError
from auth.session_manager import SessionManager
from navigation.profile_navigator import find_profile_url
from capture.screenshot_engine import capture_profile_sections
from ocr.ocr_engine import OCREngine
from preprocessing.text_cleaner import clean_ocr_text
from extraction.llm_extractor import extract_profile_data
from validation.schema import validate_profile
from storage.db_handler import DBHandler

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="LinkedIn Profile Extractor", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"
SCREENSHOTS_DIR = Path(config.SCREENSHOT_DIR)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")

# In-memory job tracking
_jobs: dict[str, dict] = {}

setup_logger()


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── API: Start Extraction ─────────────────────────────────────────────────────

@app.post("/api/extract")
async def start_extraction(request: Request):
    """
    Kick off profile extraction in the background.

    Body JSON: { "query": "Elon Musk" }  or  { "query": "https://linkedin.com/in/elon-musk" }
    Returns: { "job_id": "..." }
    """
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "progress": [],
        "screenshots": [],
        "profile": None,
        "error": None,
        "done": False,
    }

    # Run pipeline in background
    asyncio.create_task(_run_pipeline(job_id, query))
    return {"job_id": job_id}


# ── API: Stream Progress via SSE ──────────────────────────────────────────────

@app.get("/api/progress/{job_id}")
async def stream_progress(job_id: str):
    """Server-Sent Events stream for real-time progress updates."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_idx = 0
        while True:
            job = _jobs[job_id]
            # Send any new progress messages
            new_msgs = job["progress"][last_idx:]
            for msg in new_msgs:
                yield f"data: {json.dumps(msg)}\n\n"
            last_idx = len(job["progress"])

            if job["done"]:
                # Send final result
                result = {
                    "type": "done",
                    "screenshots": job["screenshots"],
                    "profile": job["profile"],
                    "error": job["error"],
                }
                yield f"data: {json.dumps(result)}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── API: Get Job Result ───────────────────────────────────────────────────────

@app.get("/api/result/{job_id}")
async def get_result(job_id: str):
    """Get the completed result for a job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    if not job["done"]:
        return JSONResponse({"status": "running", "progress": job["progress"]})
    return {
        "status": "done",
        "screenshots": job["screenshots"],
        "profile": job["profile"],
        "error": job["error"],
    }


# ── API: List Past Profiles ──────────────────────────────────────────────────

@app.get("/api/profiles")
async def list_profiles():
    """Return all previously extracted profiles from the database."""
    try:
        db = DBHandler()
        rows = db.conn.execute(
            "SELECT id, full_name, profile_url, raw_json, extracted_at FROM profiles ORDER BY id DESC"
        ).fetchall()
        db.close()
        profiles = []
        for row in rows:
            data = json.loads(row["raw_json"]) if row["raw_json"] else {}
            profiles.append({
                "id": row["id"],
                "full_name": row["full_name"],
                "profile_url": row["profile_url"],
                "headline": data.get("headline"),
                "extracted_at": row["extracted_at"],
            })
        return {"profiles": profiles}
    except Exception as exc:
        logger.error("Failed to list profiles: {}", exc)
        return {"profiles": []}


# ── Background Pipeline ──────────────────────────────────────────────────────

async def _run_pipeline(job_id: str, query: str):
    """Execute the full extraction pipeline, posting progress updates."""
    job = _jobs[job_id]
    pw = None
    browser = None

    def progress(message: str, step: str = "info"):
        job["progress"].append({"type": "progress", "step": step, "message": message})

    try:
        from playwright.async_api import async_playwright

        # Determine if query is a URL or a name
        is_url = query.startswith("http") and "/in/" in query
        progress("Starting extraction pipeline...", "start")

        # ── Browser Launch ─────────────────────────────────────────────
        progress("Launching browser...", "browser")
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=config.HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,900",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        # Session handling
        cookies_path = Path(config.COOKIES_PATH)
        use_saved = cookies_path.exists()
        context = None
        page = None

        if use_saved:
            progress("Loading saved session...", "auth")
            context = await browser.new_context(
                storage_state=str(cookies_path),
                viewport={"width": 1280, "height": 900},
            )
            session_valid = await SessionManager.load_session(context)
            if not session_valid:
                progress("Saved session expired — logging in fresh...", "auth")
                await context.close()
                use_saved = False

        if not use_saved:
            context = await browser.new_context()
            page = await context.new_page()
            progress("Logging into LinkedIn...", "auth")
            try:
                await SessionManager.login(page)
                progress("Login successful ✓", "auth")
            except CaptchaError:
                progress("CAPTCHA detected — cannot proceed automatically", "error")
                job["error"] = "LinkedIn CAPTCHA detected. Please solve it manually or try again later."
                return
            except Exception as exc:
                progress(f"Login failed: {exc}", "error")
                job["error"] = f"Login failed: {exc}"
                return

        if page is None:
            page = await context.new_page()

        # ── Find Profile URL ──────────────────────────────────────────
        if is_url:
            profile_url = query
            progress(f"Using provided URL: {profile_url}", "search")
        else:
            progress(f"Searching for '{query}' on LinkedIn...", "search")
            try:
                profile_url = await find_profile_url(page, query)
                progress(f"Found profile: {profile_url}", "search")
            except ProfileNotFoundError:
                progress(f"No profile found for '{query}'", "error")
                job["error"] = f"No LinkedIn profile found for '{query}'."
                return

        # ── Capture Screenshots ───────────────────────────────────────
        progress("Capturing profile sections...", "capture")
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_paths = await capture_profile_sections(page, profile_url)
        progress(f"Captured {len(screenshot_paths)} screenshots ✓", "capture")

        # Store relative paths for the web
        relative_paths = []
        for p in screenshot_paths:
            rel = os.path.relpath(p, start=str(Path(config.SCREENSHOT_DIR).parent))
            relative_paths.append("/" + rel.replace("\\", "/"))
        job["screenshots"] = relative_paths

        # ── OCR ───────────────────────────────────────────────────────
        progress("Running OCR on screenshots...", "ocr")
        ocr_engine = OCREngine()
        raw_ocr = ocr_engine.extract_from_all_sections(screenshot_paths)
        if not raw_ocr.strip():
            progress("OCR returned empty text", "error")
            job["error"] = "OCR failed — no text could be extracted."
            return
        progress(f"OCR complete — {len(raw_ocr)} characters extracted ✓", "ocr")

        # ── Clean Text ────────────────────────────────────────────────
        progress("Cleaning OCR text...", "clean")
        cleaned_text = clean_ocr_text(raw_ocr)
        progress("Text cleaned ✓", "clean")

        # ── LLM Extraction ────────────────────────────────────────────
        progress("Extracting structured data via LLM (this may take a minute)...", "llm")
        try:
            raw_dict = await extract_profile_data(cleaned_text)
            progress("LLM extraction complete ✓", "llm")
        except LLMParseError:
            progress("LLM failed to return valid JSON after retries", "error")
            job["error"] = "LLM extraction failed after 3 attempts."
            return

        # ── Validate ──────────────────────────────────────────────────
        progress("Validating profile data...", "validate")
        try:
            profile = validate_profile(raw_dict)
            progress("Validation passed ✓", "validate")
        except Exception as exc:
            progress(f"Validation error: {exc}", "error")
            profile = None

        # ── Save to DB ────────────────────────────────────────────────
        if profile:
            progress("Saving to database...", "save")
            db = DBHandler()
            db.save_profile(profile, profile_url)
            db.close()
            progress("Profile saved ✓", "save")
            job["profile"] = json.loads(profile.model_dump_json())
        else:
            job["profile"] = raw_dict

        progress("Extraction complete!", "done")

    except Exception as exc:
        logger.exception("Pipeline error: {}", exc)
        job["error"] = str(exc)
        job["progress"].append({"type": "progress", "step": "error", "message": str(exc)})

    finally:
        # Always clean up browser and Playwright
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass
        job["done"] = True


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Web UI ready at http://localhost:8000")
