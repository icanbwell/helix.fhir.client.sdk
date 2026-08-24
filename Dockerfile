FROM public.ecr.aws/docker/library/python:3.12-alpine3.20

COPY --from=ghcr.io/astral-sh/uv:0.11.6@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754 /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/opt/venv/bin:$PATH"

# Install system dependencies
RUN apk add --no-cache \
    make \
    git \
    build-base \
    python3-dev \
    libffi-dev \
    openssl-dev

# Set working directory
WORKDIR /src

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock* /src/

# Install project dependencies
RUN uv sync --frozen --all-groups --no-install-project --verbose

# Copy the rest of the project files
COPY . /src

# Creating and switching to non root user
RUN addgroup -g 1001 nonrootgroup && \
    adduser -u 1001 -G nonrootgroup -s /bin/sh -D nonrootuser && \
    chown -R nonrootuser:nonrootgroup /opt/venv /src

USER nonrootuser
