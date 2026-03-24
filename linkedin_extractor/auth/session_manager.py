"""
auth/session_manager.py — LinkedIn login and cookie-based session persistence.
"""

import json
from pathlib import Path

from loguru import logger
from playwright.async_api import Page, BrowserContext

from config import LOGIN_URL, COOKIES_PATH, LINKEDIN_EMAIL, LINKEDIN_PASSWORD, LINKEDIN_BASE_URL
from utils.exceptions import CaptchaError, SessionExpiredError
from utils.rate_limiter import random_delay


class SessionManager:
    """Handle LinkedIn authentication with cookie persistence."""

    # ── Login ──────────────────────────────────────────────────────────────────

    @staticmethod
    async def login(page: Page, email: str | None = None, password: str | None = None) -> bool:
        """
        Perform a full email/password login on LinkedIn.

        Args:
            page: Playwright Page (must belong to a BrowserContext).
            email: Override email (falls back to .env value).
            password: Override password (falls back to .env value).

        Returns:
            True on successful login.

        Raises:
            CaptchaError: If LinkedIn presents a CAPTCHA challenge.
            RuntimeError: On unexpected login failure.
        """
        _email = email or LINKEDIN_EMAIL
        _password = password or LINKEDIN_PASSWORD

        if not _email or not _password:
            raise RuntimeError("LinkedIn credentials not provided. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env")

        logger.info("Navigating to LinkedIn login page")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await random_delay()

        # Fill credentials
        logger.debug("Filling login form")
        await page.fill("#username", _email)
        await page.fill("#password", _password)
        await random_delay()

        # Submit
        logger.info("Submitting login form")
        await page.click('[data-litms-control-urn="login-submit"]')

        # Wait for navigation to complete
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

        current_url = page.url

        # Check for CAPTCHA / challenge
        if "challenge" in current_url or "checkpoint" in current_url:
            logger.error("CAPTCHA / security challenge detected at {}", current_url)
            raise CaptchaError()

        # Check for successful redirect to feed
        if "/feed" in current_url:
            logger.success("Login successful — redirected to feed")
            await SessionManager._save_cookies(page.context)
            return True

        # Fallback: check page content for challenge indicators
        page_content = await page.content()
        if "challenge" in page_content.lower():
            logger.error("CAPTCHA detected in page body")
            raise CaptchaError()

        logger.warning("Login may have failed — current URL: {}", current_url)
        raise RuntimeError(f"Login failed. Ended up at: {current_url}")

    # ── Load Saved Session ─────────────────────────────────────────────────────

    @staticmethod
    async def load_session(context: BrowserContext) -> bool:
        """
        Verify whether a saved cookie file yields a valid LinkedIn session.

        Args:
            context: BrowserContext that was created with storage_state=COOKIES_PATH.

        Returns:
            True if the session is still valid, False otherwise.
        """
        cookies_file = Path(COOKIES_PATH)
        if not cookies_file.exists():
            logger.info("No saved cookies found at {}", COOKIES_PATH)
            return False

        logger.info("Cookies file found — verifying session validity")
        page = await context.new_page()
        try:
            await page.goto(f"{LINKEDIN_BASE_URL}/feed", wait_until="domcontentloaded", timeout=15000)
            await random_delay()

            current_url = page.url
            if "/feed" in current_url:
                logger.success("Saved session is valid")
                return True

            logger.warning("Session invalid — redirected to {}", current_url)
            return False
        except Exception as exc:
            logger.warning("Session verification failed: {}", exc)
            return False
        finally:
            await page.close()

    # ── Internal Helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _save_cookies(context: BrowserContext) -> None:
        """Persist browser cookies to disk."""
        cookies_dir = Path(COOKIES_PATH).parent
        cookies_dir.mkdir(parents=True, exist_ok=True)
        storage = await context.storage_state()
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            json.dump(storage, f, indent=2)
        logger.info("Cookies saved to {}", COOKIES_PATH)
