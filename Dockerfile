FROM 856965016623.dkr.ecr.us-east-1.amazonaws.com/root-mirror/python:3.12-alpine3.22

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/opt/venv/bin:$PATH"

# .rootioignore lists package@version patches rootio_patcher must skip (with the
# reasoning for each). The patcher auto-discovers it from the working directory.
COPY .rootioignore /src/.rootioignore

# SECURITY: repository credentials are written, used, and stripped inside this single
# RUN. Splitting them across instructions bakes them into an intermediate layer that is
# recoverable with `docker save`/`docker history`.
RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    set -eu && \
    ALPINE_MINOR=$(cat /etc/alpine-release | cut -d. -f1,2) && \
    echo "machine artifacts.bwell.com login $(cat /run/secrets/jfrog_read_user) password $(cat /run/secrets/jfrog_read_token)" > ~/.netrc && \
    chmod 600 ~/.netrc && \
    AUTH_HEADER="Authorization: Basic $(printf '%s:%s' "$(cat /run/secrets/jfrog_read_user)" "$(cat /run/secrets/jfrog_read_token)" | base64 | tr -d '\n')" && \
    wget -qO /etc/apk/keys/alpine.rsa.pub --header="$AUTH_HEADER" \
        "https://artifacts.bwell.com/artifactory/api/security/keypair/public/repositories/private-alpine" && \
    wget -qO "/etc/apk/keys/root@alpinelinux.org.rsa.pub" --header="$AUTH_HEADER" \
        "https://artifacts.bwell.com/artifactory/vendor-public-keys/rootio-alpine.pub" && \
    echo "https://artifacts.bwell.com/artifactory/rootio-alpine/${ALPINE_MINOR}"            >  /etc/apk/repositories && \
    echo "https://artifacts.bwell.com/artifactory/global-alpine/v${ALPINE_MINOR}/main"      >> /etc/apk/repositories && \
    echo "https://artifacts.bwell.com/artifactory/global-alpine/v${ALPINE_MINOR}/community" >> /etc/apk/repositories && \
    echo "https://artifacts.bwell.com/artifactory/private-alpine/main/${ALPINE_MINOR}"      >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache secure-apk && \
    apk add --no-cache rootio-patcher && \
    apk add --no-cache uv make git build-base python3-dev libffi-dev openssl-dev && \
    rm -f ~/.netrc

# Set working directory
WORKDIR /src

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock* /src/

# Install project dependencies
RUN --mount=type=secret,id=jfrog_read_token \
    set -eu && \
    export UV_INDEX_JFROG_USERNAME="" && \
    export UV_INDEX_JFROG_PASSWORD="$(cat /run/secrets/jfrog_read_token)" && \
    uv sync --frozen --all-groups --no-install-project --verbose

# rootio_patcher shells out to `pip list`; uv-managed venvs don't ship pip. Install the
# Root.io-patched build directly (already published on the JFrog mirror) rather than the
# vanilla ensurepip one, so the patcher's own bootstrap doesn't trip its own CVE gate.
RUN --mount=type=secret,id=jfrog_read_token \
    set -eu && \
    export UV_INDEX_JFROG_USERNAME="" && \
    export UV_INDEX_JFROG_PASSWORD="$(cat /run/secrets/jfrog_read_token)" && \
    uv pip install "pip==25.0.1+aikido.5"

# Fail the build if any installed package has a Root.io patched version we are not using.
RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    set -eu && \
    echo "machine artifacts.bwell.com login $(cat /run/secrets/jfrog_read_user) password $(cat /run/secrets/jfrog_read_token)" > ~/.netrc && \
    chmod 600 ~/.netrc && \
    ROOTIO_PKG_URL=https://artifacts.bwell.com/artifactory/api \
    ROOTIO_PIP_INDEX_URL=https://artifacts.bwell.com/artifactory/api/pypi/virtual-pypi/simple \
    rootio_patcher pip remediate --dry-run --python-path=/opt/venv/bin/python && \
    rm -f ~/.netrc

# Copy the rest of the project files
COPY . /src

# Install the project itself and prune build-only deps (pip, etc.) from the final image
RUN --mount=type=secret,id=jfrog_read_token \
    set -eu && \
    export UV_INDEX_JFROG_USERNAME="" && \
    export UV_INDEX_JFROG_PASSWORD="$(cat /run/secrets/jfrog_read_token)" && \
    uv sync --frozen --all-groups

# Creating and switching to non root user
RUN addgroup -g 1001 nonrootgroup && \
    adduser -u 1001 -G nonrootgroup -s /bin/sh -D nonrootuser && \
    chown -R nonrootuser:nonrootgroup /opt/venv /src

USER nonrootuser
