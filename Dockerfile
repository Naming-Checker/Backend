FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

# Playwright browser binaries (~400MB+) are optional (stage2 scrapers only).
# Set INSTALL_PLAYWRIGHT_BROWSERS=true at build time when scrapers are needed on the host.
ARG INSTALL_PLAYWRIGHT_BROWSERS=true
RUN if [ "$INSTALL_PLAYWRIGHT_BROWSERS" = "true" ]; then playwright install --with-deps chromium; fi

EXPOSE 8000

CMD ["python", "src/manage.py", "run-server"]
