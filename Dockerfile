FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system microscore \
    && useradd --system --gid microscore --home-dir /app microscore

COPY pyproject.toml README.md ./
COPY src ./src
COPY data/raw ./data/raw
COPY data/external ./data/external
COPY migrations ./migrations

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[app]"

USER microscore

EXPOSE 8010

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=2)"]

CMD ["python", "-m", "uvicorn", "microscore_api.main:app", "--host", "0.0.0.0", "--port", "8010"]
