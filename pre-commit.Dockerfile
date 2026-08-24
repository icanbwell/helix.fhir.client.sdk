FROM public.ecr.aws/docker/library/python:3.12-alpine3.20

COPY --from=ghcr.io/astral-sh/uv:0.11.6@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754 /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/opt/venv/bin:$PATH"

# Install git and build-essential
RUN apk add --no-cache git build-base

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install all dependencies including dev group (pre-commit linters need dev imports)
RUN uv sync --frozen --all-groups --no-install-project --verbose

# Set the working directory
WORKDIR /sourcecode

# Clean up unnecessary files
RUN git config --global --add safe.directory /sourcecode

# Creating and switching to non root user
RUN addgroup -g 1001 nonrootgroup && \
    adduser -u 1001 -G nonrootgroup -s /bin/sh -D nonrootuser && \
    chown -R nonrootuser:nonrootgroup /opt/venv

USER nonrootuser

# Define the command to run
CMD ["pre-commit", "run", "--all-files"]
