# Stub Dockerfile for local dev. Production image hardened in Phase 1.5 CD work.
FROM python:3.11-slim

WORKDIR /app

# System deps for docling (libmagic, poppler for PDF, libreoffice for DOCX fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir uv && uv pip install --system -e .

EXPOSE 8000

CMD ["uvicorn", "cc_distribution_parser.main:app", "--host", "0.0.0.0", "--port", "8000"]
