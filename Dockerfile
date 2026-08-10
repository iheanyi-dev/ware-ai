# syntax=docker/dockerfile:1

# Playwright's official image ships Python + Chromium + every OS-level
# dependency Chromium needs (libnss3, libatk, etc.) already installed and
# version-matched. Doing this by hand with apt is fragile and easy to get
# out of sync with the `playwright` pip package version — this avoids that.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# Prevents Python from writing .pyc files and buffering stdout/stderr,
# so logs show up immediately in `docker logs` instead of being buffered.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install uv itself (pinned via COPY --from, avoids needing curl/pip in image)
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Copy only dependency manifests first so this layer is cached and only
# rebuilds when pyproject.toml/uv.lock actually change, not on every
# code edit.
COPY pyproject.toml uv.lock ./

# --frozen: fail if uv.lock is out of sync with pyproject.toml, rather than
# silently re-resolving (keeps the container's deps identical to what you
# tested locally). --no-dev: skip dev/test dependencies in the runtime image.
RUN uv sync --frozen --no-dev --no-install-project

# Now copy the rest of the app
COPY . .

# Install the project itself (separate from deps above, so app-code edits
# don't invalidate the dependency-install layer cached above)
RUN uv sync --frozen --no-dev

# Run as a non-root user rather than the image's default root — standard
# container hardening practice.
RUN groupadd -r app && useradd -r -g app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# `uv run` uses the project's own virtualenv (created by uv sync above)
# without needing to manually activate it.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]