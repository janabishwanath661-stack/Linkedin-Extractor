"""
config.py — Central configuration for the LinkedIn Profile Extractor.
All constants are defined here. Other modules import from this file only.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# ── LinkedIn URLs ──────────────────────────────────────────────────────────────
LINKEDIN_BASE_URL = "https://www.linkedin.com"
LOGIN_URL = "https://www.linkedin.com/login"
SEARCH_URL = "https://www.linkedin.com/search/results/people/"

# ── Project Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = str(BASE_DIR / "auth" / "cookies.json")
SCREENSHOT_DIR = str(BASE_DIR / "screenshots")
DB_PATH = str(BASE_DIR / "storage" / "profiles.db")

# ── Credentials (read from .env) ──────────────────────────────────────────────
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# ── LLM Configuration (Hugging Face) ──────────────────────────────────────────
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
HF_DEVICE = os.getenv("HF_DEVICE", "auto")           # "auto", "cpu", "cuda"
HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "2048"))

# ── Rate Limiting ─────────────────────────────────────────────────────────────
MIN_DELAY = 2.5   # seconds between actions
MAX_DELAY = 5.0   # seconds between actions

# ── Browser ───────────────────────────────────────────────────────────────────
HEADLESS = True    # set False for debugging

# ── Scroll Sections ───────────────────────────────────────────────────────────
SCROLL_SECTIONS = [
    {"name": "header",        "scroll_y": 0},
    {"name": "about",         "scroll_y": 450},
    {"name": "experience_1",  "scroll_y": 950},
    {"name": "experience_2",  "scroll_y": 1500},
    {"name": "education",     "scroll_y": 2100},
    {"name": "skills",        "scroll_y": 2700},
    {"name": "certifications","scroll_y": 3200},
    {"name": "contact_info",  "scroll_y": 3700},
]
