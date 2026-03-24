"""
ocr/ocr_engine.py — PaddleOCR wrapper for extracting text from profile screenshots.
"""

from loguru import logger


class OCREngine:
    """Wrapper around PaddleOCR for batch text extraction from images."""

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        logger.info("Initialising PaddleOCR engine")
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        logger.info("PaddleOCR engine ready")

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Run OCR on a single image and return the merged text.

        Args:
            image_path: Path to a PNG screenshot.

        Returns:
            Newline-joined text blocks with confidence ≥ 0.6.
        """
        try:
            result = self.ocr.ocr(image_path, cls=True)
        except Exception as exc:
            logger.error("OCR failed for {}: {}", image_path, exc)
            return ""

        if not result or not result[0]:
            logger.warning("No text detected in {}", image_path)
            return ""

        lines: list[str] = []
        for line_info in result[0]:
            # Each line_info: [bbox, (text, confidence)]
            if line_info and len(line_info) >= 2:
                text, confidence = line_info[1]
                if confidence >= 0.6:
                    lines.append(text)

        merged = "\n".join(lines)
        logger.debug("Extracted {} lines from {}", len(lines), image_path)
        return merged

    def extract_from_all_sections(self, image_paths: list[str]) -> str:
        """
        Run OCR on every screenshot and join with section breaks.

        Args:
            image_paths: Ordered list of screenshot file paths.

        Returns:
            Combined OCR text with section delimiters.
        """
        section_texts: list[str] = []
        for path in image_paths:
            text = self.extract_text_from_image(path)
            if text:
                section_texts.append(text)

        combined = "\n\n--- SECTION BREAK ---\n\n".join(section_texts)
        logger.info("Combined OCR text length: {} characters", len(combined))
        return combined
