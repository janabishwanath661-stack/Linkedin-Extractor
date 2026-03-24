"""
utils/exceptions.py — Custom exception classes for the LinkedIn Profile Extractor.
"""


class CaptchaError(Exception):
    """LinkedIn presented a CAPTCHA challenge during login."""

    def __init__(self, message: str = "LinkedIn CAPTCHA detected. Please solve it manually or try again later."):
        super().__init__(message)


class ProfileNotFoundError(Exception):
    """Search returned no results for the given name."""

    def __init__(self, name: str = ""):
        message = f"No LinkedIn profile found for '{name}'." if name else "No LinkedIn profile found."
        super().__init__(message)


class SessionExpiredError(Exception):
    """Saved cookies are invalid or the session has expired."""

    def __init__(self, message: str = "LinkedIn session expired. A fresh login is required."):
        super().__init__(message)


class OCRFailedError(Exception):
    """All screenshots returned empty text after OCR processing."""

    def __init__(self, message: str = "OCR failed — no text could be extracted from any screenshot."):
        super().__init__(message)


class LLMParseError(Exception):
    """Ollama returned invalid JSON after maximum retry attempts."""

    def __init__(self, attempts: int = 3):
        message = f"LLM returned invalid JSON after {attempts} attempts."
        super().__init__(message)
