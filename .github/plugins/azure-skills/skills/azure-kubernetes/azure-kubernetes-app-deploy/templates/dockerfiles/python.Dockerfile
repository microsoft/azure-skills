# =============================================================================
# Python Production Dockerfile
# =============================================================================
# Customize the following before use:
#   - APP_MODULE:  Change the uvicorn target (e.g. "app.main:app" for FastAPI,
#                  "myproject.wsgi:application" for Django with gunicorn)
#   - PORT:        Change EXPOSE port if not 8000
#   - DEPS FILE:   If using Poetry, replace requirements.txt steps with
#                  "poetry export -f requirements.txt" in the build stage
#   - ENTRY_POINT: Adjust the final CMD for your framework (gunicorn, uvicorn,
#                  flask run, etc.)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
# Base: latest stable Python, Debian-slim (NOT Alpine — musl breaks many C extensions). See references/base-images.md.
FROM python:<LATEST_STABLE_PYTHON>-slim AS build

WORKDIR /app

# Create a virtual environment so we can copy it cleanly to the runtime stage
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Layer caching: install dependencies before copying source
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# If you have a build step (e.g. Django collectstatic), run it here:
# RUN python manage.py collectstatic --noinput

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:<LATEST_STABLE_PYTHON>-slim

WORKDIR /app

# AKS Deployment Safeguards DS004: create and switch to a non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/sh --create-home appuser

# Copy the virtual environment and application source from the build stage
COPY --from=build --chown=appuser:appuser /app /app

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

# HEALTHCHECK is omitted — Kubernetes liveness/readiness probes handle health
# checks in AKS. Adding a Dockerfile HEALTHCHECK would require installing curl
# in the runtime image, increasing size and attack surface.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
