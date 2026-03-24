# LinkedIn Profile Extractor

A Python CLI tool that automates LinkedIn profile extraction using Playwright (async browser automation), PaddleOCR (optical character recognition), and a local Hugging Face LLM to produce validated structured JSON profiles.

## Prerequisites

- **Docker** & **Docker Compose** (recommended), OR
- Python 3.11+ installed locally
- ~16 GB RAM (for loading the 7B model) or a CUDA GPU

---

## Option A — Docker (Recommended)

### 1. Configure credentials

```bash
cp .env.example .env
# Edit .env with your LinkedIn email and password
```

### 2. Build & run

```bash
docker compose build
docker compose run extractor --name "Elon Musk" --export json
```

The first run will download the Qwen2.5-7B-Instruct model (~14 GB). Weights are cached in a Docker volume so subsequent runs start fast.

#### GPU support (optional)

Uncomment the `deploy` block in `docker-compose.yml` and ensure `nvidia-container-toolkit` is installed.

#### Use a different model

```bash
HF_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3 docker compose run extractor --name "Elon Musk"
```

### 3. Stop

```bash
docker compose down
```

---

## Option B — Local Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

```bash
cp .env.example .env
# Edit .env
```

```bash
python main.py --name "Elon Musk" --export json
```

---

## CLI Arguments

| Argument        | Required | Default      | Description                          |
|-----------------|----------|--------------|--------------------------------------|
| `--name`        | Yes      | —            | Full name of the person to search    |
| `--email`       | No       | from .env    | Override LinkedIn email              |
| `--password`    | No       | from .env    | Override LinkedIn password           |
| `--export`      | No       | `json`       | Export format: `json`, `csv`, `both` |
| `--output`      | No       | `./results/` | Output directory for exports         |
| `--headless`    | No       | `true`       | Run browser headless (`true`/`false`)|
| `--fresh-login` | No       | `false`      | Ignore saved cookies, force login    |

## Environment Variables

| Variable            | Default                       | Description                       |
|---------------------|-------------------------------|-----------------------------------|
| `HF_MODEL_NAME`     | `Qwen/Qwen2.5-7B-Instruct`   | Hugging Face model ID             |
| `HF_DEVICE`         | `auto`                        | `auto`, `cpu`, or `cuda`          |
| `HF_MAX_NEW_TOKENS` | `2048`                        | Max generation length             |

## Project Structure

```
linkedin_extractor/
├── main.py                   # CLI entry point
├── config.py                 # All constants
├── Dockerfile                # Python 3.11 container
├── docker-compose.yml        # Extractor service
├── auth/
│   └── session_manager.py    # Login + cookie persistence
├── navigation/
│   └── profile_navigator.py  # Search + find profile URL
├── capture/
│   └── screenshot_engine.py  # Sectional screenshot capture
├── ocr/
│   └── ocr_engine.py         # PaddleOCR wrapper
├── preprocessing/
│   └── text_cleaner.py       # OCR text cleanup
├── extraction/
│   └── llm_extractor.py      # HuggingFace LLM extraction
├── validation/
│   └── schema.py             # Pydantic models
├── storage/
│   └── db_handler.py         # SQLite + JSON/CSV export
├── utils/
│   ├── exceptions.py         # Custom exceptions
│   ├── rate_limiter.py       # Async delay helpers
│   └── logger.py             # Loguru setup
└── screenshots/              # Temp folder (gitignored)
```
