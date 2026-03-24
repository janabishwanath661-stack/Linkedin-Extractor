"""
main.py — CLI entry point for the LinkedIn Profile Extractor.

Usage:
    python main.py --name "Elon Musk" --export json
    python main.py --name "Satya Nadella" --export both --output ./results/ --headless false
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.table import Table

# ── Ensure project root is on sys.path ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

console = Console()


# ── Argument Parsing ───────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LinkedIn Profile Extractor — extract structured profile data via screenshots + OCR + LLM"
    )
    parser.add_argument("--name", required=True, help="Full name of the person to search on LinkedIn")
    parser.add_argument("--email", default=None, help="Override LINKEDIN_EMAIL from .env")
    parser.add_argument("--password", default=None, help="Override LINKEDIN_PASSWORD from .env")
    parser.add_argument("--export", choices=["json", "csv", "both"], default="json", help="Export format (default: json)")
    parser.add_argument("--output", default="./results/", help="Output directory for exports (default: ./results/)")
    parser.add_argument("--headless", choices=["true", "false"], default="true", help="Run browser headless (default: true)")
    parser.add_argument("--fresh-login", action="store_true", help="Ignore saved cookies and force a new login")
    return parser.parse_args()


# ── Main Async Pipeline ───────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    # 1. Setup logger
    setup_logger()
    logger.info("=== LinkedIn Profile Extractor started ===")
    logger.info("Target: {}", args.name)

    headless = args.headless == "true"
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Launch Playwright
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        # 3. Browser setup
        cookies_path = Path(config.COOKIES_PATH)
        use_saved_session = cookies_path.exists() and not args.fresh_login

        if use_saved_session:
            logger.info("Attempting to reuse saved session")
            browser = await pw.chromium.launch(headless=headless)
            context = await browser.new_context(storage_state=str(cookies_path))
            session_valid = await SessionManager.load_session(context)
            if not session_valid:
                logger.warning("Saved session invalid — performing fresh login")
                await context.close()
                await browser.close()
                use_saved_session = False

        if not use_saved_session:
            browser = await pw.chromium.launch(headless=headless)
            context = await browser.new_context()

        page = await context.new_page()

        try:
            # 4. Login if needed
            if not use_saved_session:
                max_login_attempts = 3
                for attempt in range(1, max_login_attempts + 1):
                    try:
                        logger.info("Login attempt {}/{}", attempt, max_login_attempts)
                        await SessionManager.login(page, email=args.email, password=args.password)
                        break
                    except CaptchaError:
                        logger.critical("CAPTCHA detected — cannot proceed automatically")
                        console.print("[bold red]❌ LinkedIn CAPTCHA detected.[/] Please solve it manually or try again later.")
                        await browser.close()
                        return
                    except Exception as exc:
                        logger.error("Login attempt {} failed: {}", attempt, exc)
                        if attempt == max_login_attempts:
                            console.print(f"[bold red]❌ Login failed after {max_login_attempts} attempts.[/]")
                            await browser.close()
                            return
                        await asyncio.sleep(2 ** attempt)

            # 5. Find profile URL
            try:
                profile_url = await find_profile_url(page, args.name)
            except ProfileNotFoundError as exc:
                console.print(f"[bold red]❌ {exc}[/]")
                await browser.close()
                return

            # 6. Capture screenshots
            screenshot_paths = await capture_profile_sections(page, profile_url)

            # 7. OCR
            logger.info("Running OCR on {} screenshots", len(screenshot_paths))
            ocr_engine = OCREngine()
            raw_ocr = ocr_engine.extract_from_all_sections(screenshot_paths)

            if not raw_ocr.strip():
                raise OCRFailedError()

            # 8. Clean OCR text
            cleaned_text = clean_ocr_text(raw_ocr)
            logger.info("Cleaned OCR text: {} characters", len(cleaned_text))

            # 9. LLM extraction
            try:
                raw_dict = await extract_profile_data(cleaned_text)
            except LLMParseError as exc:
                console.print(f"[bold red]❌ {exc}[/]")
                await browser.close()
                return

            # 10. Validate
            profile = validate_profile(raw_dict)

            # 11. Save to DB
            db = DBHandler()
            db.save_profile(profile, profile_url)

            # 12. Export
            if args.export in ("json", "both"):
                json_path = str(output_dir / f"{profile.full_name.replace(' ', '_')}.json")
                db.export_json(profile.full_name, json_path)

            if args.export in ("csv", "both"):
                csv_path = str(output_dir / "profiles.csv")
                db.export_csv(csv_path)

            db.close()

            # 13. Rich summary table
            _print_summary(profile)

            # 14. Clean up temp screenshots
            screenshots_dir = Path(config.SCREENSHOT_DIR)
            if screenshots_dir.exists():
                shutil.rmtree(screenshots_dir)
                logger.info("Cleaned up screenshots directory")

            logger.success("=== Extraction complete ===")

        except OCRFailedError as exc:
            console.print(f"[bold red]❌ {exc}[/]")
        except Exception as exc:
            logger.exception("Unexpected error: {}", exc)
            console.print(f"[bold red]❌ Unexpected error: {exc}[/]")
        finally:
            await browser.close()


def _print_summary(profile) -> None:
    """Print a rich table summarising the extracted profile."""
    table = Table(title="📋 Extracted LinkedIn Profile", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Name", profile.full_name)
    table.add_row("Headline", profile.headline or "—")
    table.add_row("Location", profile.location or "—")
    table.add_row("Current Company", profile.current_company or "—")
    table.add_row("Connections", profile.connections or "—")
    table.add_row("# Experience", str(len(profile.experience)))
    table.add_row("# Education", str(len(profile.education)))
    table.add_row("# Skills", str(len(profile.skills)))
    table.add_row("# Certifications", str(len(profile.certifications)))
    table.add_row("# Languages", str(len(profile.languages)))
    table.add_row("Email", profile.email or "—")
    table.add_row("Website", profile.website or "—")

    console.print()
    console.print(table)
    console.print()


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run(parse_args()))
