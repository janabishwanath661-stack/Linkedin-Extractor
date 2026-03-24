"""
capture/screenshot_engine.py — Scroll through LinkedIn profile sections and take screenshots.
"""

import re
from pathlib import Path

from loguru import logger
from playwright.async_api import Page

from config import SCREENSHOT_DIR, SCROLL_SECTIONS
from utils.rate_limiter import random_delay, human_scroll_delay


async def capture_profile_sections(page: Page, profile_url: str) -> list[str]:
    """
    Navigate to a LinkedIn profile and capture sectional screenshots.

    Args:
        page: Authenticated Playwright Page.
        profile_url: Full LinkedIn profile URL (e.g. https://www.linkedin.com/in/username/).

    Returns:
        List of file paths to saved PNG screenshots.
    """
    # Ensure screenshots directory exists
    screenshot_dir = Path(SCREENSHOT_DIR)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    profile_slug = _extract_slug(profile_url)
    logger.info("Capturing sections for profile: {}", profile_slug)

    await page.goto(profile_url, wait_until="domcontentloaded")

    # Wait for profile content to render
    try:
        await page.wait_for_selector('[data-view-name="profile-card"], h1', timeout=10000)
    except Exception:
        logger.warning("Profile content selectors not found — continuing anyway")

    await random_delay()

    screenshot_paths: list[str] = []

    for section in SCROLL_SECTIONS:
        name = section["name"]
        scroll_y = section["scroll_y"]

        logger.debug("Scrolling to section '{}' (y={})", name, scroll_y)
        await page.evaluate(f"window.scrollTo(0, {scroll_y})")
        await page.wait_for_timeout(1800)  # Let lazy-loaded content settle

        file_path = str(screenshot_dir / f"{profile_slug}_{name}.png")
        await page.screenshot(path=file_path, full_page=False)
        screenshot_paths.append(file_path)
        logger.info("Screenshot saved: {}", file_path)

        await human_scroll_delay()

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
