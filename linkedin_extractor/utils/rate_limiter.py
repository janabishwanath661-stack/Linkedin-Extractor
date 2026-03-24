"""
utils/rate_limiter.py — Async delay helpers to mimic human browsing behaviour.
"""

import asyncio
import random

from config import MIN_DELAY, MAX_DELAY


async def random_delay() -> None:
    """Sleep for a random duration between MIN_DELAY and MAX_DELAY seconds."""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    await asyncio.sleep(delay)


async def human_scroll_delay() -> None:
    """Shorter delay used between scroll actions."""
    await asyncio.sleep(random.uniform(1.2, 2.4))
