# Sandbox image for OJ judge execution.
#
# Build expects context root with:
#   cdui/          — full CodefyUI repo (backend/ inside)
#   sandbox/       — backend/sandbox/ tree (run_judge.py, patcher.py, scoring.py)
#
# Use backend/docker/build_sandbox.{sh,ps1} to stage the build context.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install cdui dependencies. We pin CPU-only torch to keep the image small.
WORKDIR /opt
COPY cdui/ /cdui/
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.0.0" "torchvision>=0.15.0" \
    && pip install /cdui/backend

# Add sandbox scripts (run_judge.py, patcher.py, scoring.py).
COPY sandbox/ /sandbox/

# Make /sandbox importable as a package
ENV PYTHONPATH=/

ENV OJ_CDUI_PATH=/cdui/backend
ENV OJ_WORKSPACE=/workspace

# Workspace is the only writable mount; the rest of the FS should be read-only
# in production (--read-only docker flag).
WORKDIR /workspace

# Non-root user
RUN useradd -m -u 10001 judge \
    && mkdir -p /workspace \
    && chown -R judge:judge /workspace
USER judge

ENTRYPOINT ["python", "/sandbox/run_judge.py"]
