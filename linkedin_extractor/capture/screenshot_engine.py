"""
capture/screenshot_engine.py — Capture LinkedIn profile sections via full-page screenshot + PIL crop.
"""

import io
import re
from pathlib import Path

from loguru import logger
from PIL import Image
from playwright.async_api import Page

from config import SCREENSHOT_DIR, SCROLL_SECTIONS
from utils.rate_limiter import random_delay

# Viewport height used when launching the browser (must match browser context settings)
_VIEWPORT_HEIGHT = 900


async def capture_profile_sections(page: Page, profile_url: str) -> list[str]:
    """
    Navigate to a LinkedIn profile, take one full-page screenshot, then crop it
    into named sections based on the SCROLL_SECTIONS scroll-y positions.

    Args:
        page: Authenticated Playwright Page.
        profile_url: Full LinkedIn profile URL (e.g. https://www.linkedin.com/in/username/).

    Returns:
        List of file paths to saved PNG section screenshots.
    """
    screenshot_dir = Path(SCREENSHOT_DIR)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    profile_slug = _extract_slug(profile_url)
    logger.info("Capturing sections for profile: {}", profile_slug)

    # ── Font interception ─────────────────────────────────────────────────────
    # Playwright's screenshot internally awaits document.fonts.ready via CDP —
    # JS overrides don't intercept it. Aborting font network requests forces
    # document.fonts.ready to resolve immediately.
    async def _abort_fonts(route):
        await route.abort()

    await page.route("**/*.woff2", _abort_fonts)
    await page.route("**/*.woff",  _abort_fonts)
    await page.route("**/*.ttf",   _abort_fonts)
    await page.route("**/*.otf",   _abort_fonts)
    logger.debug("Font request interception active")

    # ── Navigate ──────────────────────────────────────────────────────────────
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)

    # Wait for profile content to render
    try:
        await page.wait_for_selector('[data-view-name="profile-card"], h1', timeout=10000)
    except Exception:
        logger.warning("Profile content selectors not found — continuing anyway")

    await random_delay()

    # ── Lazy-load: scroll to bottom then back to top ──────────────────────────
    # This triggers lazy-loaded sections so they appear in the full-page shot.
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(2000)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1000)

    # ── Full-page screenshot → bytes ──────────────────────────────────────────
    logger.debug("Taking full-page screenshot")
    full_bytes = await page.screenshot(full_page=True, timeout=60000)
    full_image = Image.open(io.BytesIO(full_bytes))
    img_width, img_height = full_image.size
    logger.info("Full-page screenshot: {}x{} px", img_width, img_height)

    # ── Crop into sections ────────────────────────────────────────────────────
    # Each section is a viewport-height-tall crop starting at its scroll_y offset.
    screenshot_paths: list[str] = []

    for i, section in enumerate(SCROLL_SECTIONS):
        name    = section["name"]
        top     = section["scroll_y"]
        # Bottom is the next section's top, or end of image for the last section
        if i + 1 < len(SCROLL_SECTIONS):
            bottom = SCROLL_SECTIONS[i + 1]["scroll_y"]
        else:
            bottom = img_height

        # Clamp to actual image bounds
        top    = min(top, img_height)
        bottom = min(bottom, img_height)

        if top >= bottom:
            logger.warning("Section '{}' is out of page bounds — skipping", name)
            continue

        crop_box = (0, top, img_width, bottom)
        section_img = full_image.crop(crop_box)

        file_path = str(screenshot_dir / f"{profile_slug}_{name}.png")
        section_img.save(file_path, format="PNG")
        screenshot_paths.append(file_path)
        logger.info("Section '{}' saved: {} (y={}-{})", name, file_path, top, bottom)

    logger.success("Captured {} section screenshots", len(screenshot_paths))
    return screenshot_paths


def _extract_slug(profile_url: str) -> str:
    """
    Extract the username slug from a LinkedIn profile URL.

    Example:
        https://www.linkedin.com/in/elon-musk/  →  elon-musk
    """
    match = re.search(r"/in/([^/?#]+)", profile_url)
    return match.group(1) if match else "unknown"
