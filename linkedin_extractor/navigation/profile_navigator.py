"""
navigation/profile_navigator.py — Search LinkedIn and return the profile URL for a given name.
"""

import re
from urllib.parse import quote_plus

from loguru import logger
from playwright.async_api import Page

from config import SEARCH_URL
from utils.exceptions import ProfileNotFoundError
from utils.rate_limiter import random_delay


async def find_profile_url(page: Page, full_name: str) -> str:
    """
    Search LinkedIn People for *full_name* and return the first result's profile URL.

    Args:
        page: Authenticated Playwright Page.
        full_name: The person's name to search for.

    Returns:
        Clean profile URL (e.g. https://www.linkedin.com/in/username/).

    Raises:
        ProfileNotFoundError: If no search results are found.
    """
    search_url = f"{SEARCH_URL}?keywords={quote_plus(full_name)}&origin=GLOBAL_SEARCH_HEADER"
    logger.info("Searching LinkedIn for '{}'", full_name)
    await random_delay()

    await page.goto(search_url, wait_until="domcontentloaded")

    # Wait for results container
    try:
        await page.wait_for_selector(".search-results-container", timeout=10000)
    except Exception:
        logger.warning("Search results container not found — checking for empty state")
        raise ProfileNotFoundError(full_name)

    await random_delay()

    # Grab the first result link
    link_el = await page.query_selector(".entity-result__title-text a")
    if link_el is None:
        # Try alternative selector (LinkedIn DOM changes occasionally)
        link_el = await page.query_selector('a[href*="/in/"]')

    if link_el is None:
        logger.error("No profile link found in search results for '{}'", full_name)
        raise ProfileNotFoundError(full_name)

    raw_href = await link_el.get_attribute("href") or ""
    profile_url = _clean_profile_url(raw_href)
    logger.info("Found profile URL: {}", profile_url)
    return profile_url


def _clean_profile_url(raw_url: str) -> str:
    """
    Strip query parameters from a LinkedIn profile URL.

    Example:
        Input:  https://www.linkedin.com/in/username?miniProfileUrn=...
        Output: https://www.linkedin.com/in/username/
    """
    match = re.match(r"(https?://[^/]+/in/[^/?#]+)", raw_url)
    if match:
        url = match.group(1)
        return url if url.endswith("/") else url + "/"
    return raw_url
