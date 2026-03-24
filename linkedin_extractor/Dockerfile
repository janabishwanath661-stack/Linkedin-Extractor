# ── Base image: Python 3.11 ─────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies for Playwright (Chromium) and PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    libxfixes3 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    wget \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python dependencies ─────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser + ALL its OS-level deps
RUN playwright install --with-deps chromium

# ── Copy application code ───────────────────────────────────────────────────────
COPY . .

# Create required directories
RUN mkdir -p screenshots results storage auth

# HF model cache volume
VOLUME ["/root/.cache/huggingface"]

# Expose web UI port
EXPOSE 8000

# Default: start the web UI server
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
