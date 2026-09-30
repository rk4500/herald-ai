# Stage 1: Build Stage
# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim AS builder

# Install the project into `/app`
WORKDIR /build

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1

# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project


# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /build

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# --- Stage 2: Final Stage ---
# Get plain python image for final
FROM python:3.12-slim-trixie

# Setup new workdir in new stage
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

COPY --from=builder /build/.venv /app/.venv
COPY ./src /app/src
COPY ./pyproject.toml /app
RUN mkdir -p /app/data && chown nonroot:nonroot /app/data

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

USER nonroot

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT ["python", "-m", "whatsapp_agent"]

# Run the FastAPI application by default
# Uses `uv run` to sync dependencies on startup, respecting UV_NO_DEV
# Uses `fastapi dev` to enable hot-reloading when the `watch` sync occurs
# Uses `--host 0.0.0.0` to allow access from outside the container
# Note in production, you should use `fastapi run` instead
# CMD ["uv", "run", "fastapi", "dev", "--host", "0.0.0.0", "src/uv_docker_example"]
