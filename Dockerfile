# Multi-stage build for kaznlp-toolkit.
#   docker build --target test -t kaznlp:test .   -> lint + unit tests (used by Jenkins)
#   docker build -t kaznlp:latest .                -> small runtime image (HTTP service + CLI)

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- base
FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# ---------------------------------------------------------------- test
# Same Python and the same pinned tools as GitHub Actions, so a green Jenkins
# build means the same thing as a green GitHub build.
FROM base AS test
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install -e ".[dev]"
COPY tests ./tests
COPY data ./data
RUN mkdir -p /reports \
 && ruff check . \
 && ruff format --check . \
 && pytest --junitxml=/reports/junit.xml \
           --cov=kaznlp --cov-report=xml:/reports/coverage.xml \
           --cov-report=term --cov-fail-under=90

# ---------------------------------------------------------------- build
FROM base AS build
RUN pip install "build>=1.2"
COPY pyproject.toml README.md LICENSE CHANGELOG.md CITATION.cff ./
COPY src ./src
COPY tests ./tests
COPY data ./data
RUN python -m build --wheel --outdir /dist

# ---------------------------------------------------------------- runtime
FROM base AS runtime
ARG VERSION=0.1.0
ARG GIT_COMMIT=unknown
LABEL org.opencontainers.image.title="kaznlp-toolkit" \
      org.opencontainers.image.description="Kazakh text cleaning service and data pipeline" \
      org.opencontainers.image.source="https://github.com/baattezu/kaznlp" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

COPY --from=build /dist/*.whl /tmp/
RUN pip install "$(ls /tmp/*.whl)[baseline]" && rm /tmp/*.whl \
 && useradd --create-home --uid 10001 kaznlp
COPY --chown=kaznlp data ./data
USER kaznlp

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

# default: HTTP service; any kaznlp subcommand can be passed instead, e.g.
#   docker run --rm kaznlp:latest clean data/sample.jsonl /tmp/clean.jsonl
ENTRYPOINT ["kaznlp"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
