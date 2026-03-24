# LinkedIn Profile Extractor

Extract structured LinkedIn profile data using Playwright browser automation, PaddleOCR, and a local Hugging Face LLM. Comes with both a **CLI** and a **Web UI**.

---

## Quick Start (Docker)

```bash
cp .env.example .env          # fill in your LinkedIn credentials
docker compose build
docker compose up              # web UI at http://localhost:8000
```

The first run downloads the Qwen2.5-7B-Instruct model (~14 GB). Weights are cached in a Docker volume.

### GPU Support

Uncomment the `deploy` block in `docker-compose.yml` and install `nvidia-container-toolkit`.

### Use a Different Model

```bash
HF_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3 docker compose up
```

---

## Web UI

Open **http://localhost:8000** after starting the container. The UI lets you:

1. Enter a **name** or **LinkedIn profile URL**
2. Watch **real-time progress** (login → search → screenshot → OCR → LLM → validate)
3. View results in three tabs:
   - **Profile** — structured card with experience, education, skills, etc.
   - **Screenshots** — gallery with lightbox zoom
   - **Raw JSON** — copyable JSON output

---

## CLI Usage

```bash
# Inside the container:
docker compose run extractor python main.py --name "Elon Musk" --export json

# Or locally (Python 3.11+):
python main.py --name "Elon Musk" --export both --output ./results/
```

| Argument        | Default      | Description                          |
|-----------------|--------------|--------------------------------------|
| `--name`        | required     | Person to search                     |
| `--email`       | from .env    | Override LinkedIn email              |
| `--password`    | from .env    | Override LinkedIn password           |
| `--export`      | `json`       | `json`, `csv`, or `both`            |
| `--output`      | `./results/` | Output directory                     |
| `--headless`    | `true`       | `true` or `false`                   |
| `--fresh-login` | off          | Force new login                      |

---

## Environment Variables

| Variable            | Default                       | Description              |
|---------------------|-------------------------------|--------------------------|
| `LINKEDIN_EMAIL`    | —                             | LinkedIn login email     |
| `LINKEDIN_PASSWORD` | —                             | LinkedIn login password  |
| `HF_MODEL_NAME`     | `Qwen/Qwen2.5-7B-Instruct`   | Hugging Face model ID   |
| `HF_DEVICE`         | `auto`                        | `auto`, `cpu`, `cuda`   |
| `HF_MAX_NEW_TOKENS` | `2048`                        | Max generation length   |

---

## Project Structure

```
linkedin_extractor/
├── main.py                     # CLI entry point
├── config.py                   # Constants
├── Dockerfile / docker-compose.yml
├── web/
│   ├── app.py                  # FastAPI backend + extraction API
│   └── static/
│       ├── index.html          # Web UI
│       ├── style.css           # Dark-mode design
│       └── app.js              # Frontend logic
├── auth/session_manager.py
├── navigation/profile_navigator.py
├── capture/screenshot_engine.py
├── ocr/ocr_engine.py
├── preprocessing/text_cleaner.py
├── extraction/llm_extractor.py
├── validation/schema.py
├── storage/db_handler.py
└── utils/ (exceptions, logger, rate_limiter)
```
