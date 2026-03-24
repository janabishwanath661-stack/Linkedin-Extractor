"""
extraction/llm_extractor.py — Use a local Hugging Face model to extract structured profile data from OCR text.
"""

import asyncio
import json
import re

from loguru import logger

from config import HF_MODEL_NAME, HF_DEVICE, HF_MAX_NEW_TOKENS
from utils.exceptions import LLMParseError


SYSTEM_PROMPT = """\
You are a precise data extraction engine. You receive raw OCR text scraped \
from a LinkedIn profile and must extract structured data.

RULES:
- Return ONLY valid JSON. No explanation, no markdown, no backticks.
- If a field is missing or unclear, set it to null.
- For lists (experience, education, skills), return empty list [] if none found.
- Normalize all dates to "Month YYYY" format (e.g. "Jan 2020").
- Do not invent, infer, or hallucinate any data not explicitly present.
- Deduplicate repeated entries.
"""

_USER_PROMPT_TEMPLATE = """\
Extract structured profile data from this LinkedIn OCR text and return JSON \
matching exactly this schema:

{{
  "full_name": "string",
  "headline": "string or null",
  "location": "string or null",
  "about": "string or null",
  "current_company": "string or null",
  "connections": "string or null",
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "start_date": "string or null",
      "end_date": "string or null (use Present if current)",
      "duration": "string or null",
      "location": "string or null",
      "description": "string or null"
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string or null",
      "field_of_study": "string or null",
      "start_year": "string or null",
      "end_year": "string or null"
    }}
  ],
  "skills": ["list of skill strings"],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string or null",
      "issue_date": "string or null"
    }}
  ],
  "languages": ["list of language strings"],
  "email": "string or null",
  "website": "string or null",
  "phone": "string or null"
}}

OCR TEXT:
{ocr_text}
"""

MAX_RETRIES = 3

# ── Lazy-loaded model singleton ────────────────────────────────────────────────
_pipeline = None


def _get_pipeline():
    """Load the HuggingFace model lazily on first use (avoids startup cost)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

    logger.info("Loading HuggingFace model: {}", HF_MODEL_NAME)

    tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME, trust_remote_code=True)

    # Determine device / dtype
    if HF_DEVICE == "auto":
        device_map = "auto"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    elif HF_DEVICE == "cuda":
        device_map = "cuda"
        dtype = torch.float16
    else:
        device_map = "cpu"
        dtype = torch.float32

    model = AutoModelForCausalLM.from_pretrained(
        HF_MODEL_NAME,
        torch_dtype=dtype,
        device_map=device_map,
        trust_remote_code=True,
    )

    _pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
    )
    logger.success("Model loaded successfully")
    return _pipeline


def _run_inference(messages: list[dict]) -> str:
    """Run the HF pipeline synchronously and return the generated text."""
    pipe = _get_pipeline()
    tokenizer = pipe.tokenizer

    # Build prompt using the model's chat template if available
    if hasattr(tokenizer, "apply_chat_template"):
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        # Fallback: simple concatenation
        parts = []
        for m in messages:
            role = m["role"].upper()
            parts.append(f"[{role}]\n{m['content']}")
        prompt = "\n\n".join(parts) + "\n\n[ASSISTANT]\n"

    outputs = pipe(
        prompt,
        max_new_tokens=HF_MAX_NEW_TOKENS,
        do_sample=False,
        return_full_text=False,
    )
    return outputs[0]["generated_text"]


async def extract_profile_data(ocr_text: str) -> dict:
    """
    Send OCR text to a local Hugging Face model and parse the structured JSON response.

    Retries up to MAX_RETRIES on JSON parse failures with exponential back-off.

    Args:
        ocr_text: Cleaned OCR text from all profile sections.

    Returns:
        Parsed dict matching the profile schema.

    Raises:
        LLMParseError: If all retries are exhausted without valid JSON.
    """
    user_prompt = _USER_PROMPT_TEMPLATE.format(ocr_text=ocr_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("LLM extraction attempt {}/{}", attempt, MAX_RETRIES)

        try:
            raw_content = await asyncio.to_thread(_run_inference, messages)
        except Exception as exc:
            logger.error("HF inference failed (attempt {}): {}", attempt, exc)
            await asyncio.sleep(2 ** attempt)
            continue

        # Strip accidental markdown fences
        cleaned = _strip_markdown_fences(raw_content)

        try:
            data = json.loads(cleaned)
            logger.success("LLM returned valid JSON on attempt {}", attempt)
            return data
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error on attempt {}: {}", attempt, exc)
            logger.debug("Raw LLM output:\n{}", raw_content[:500])
            await asyncio.sleep(2 ** attempt)

    logger.error("All {} LLM attempts failed to produce valid JSON", MAX_RETRIES)
    raise LLMParseError(MAX_RETRIES)


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that LLMs sometimes add."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
