FROM 856965016623.dkr.ecr.us-east-1.amazonaws.com/root-mirror/python:3.12-alpine3.20

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

# Copy Pipfile first to leverage Docker cache
COPY Pipfile* /src/

# Upgrade pip and install pipenv
RUN pip install --upgrade pip && \
    pip install --no-cache-dir pipenv

# Install project dependencies
RUN --mount=type=secret,id=jfrog_user \
    --mount=type=secret,id=jfrog_token \
    set -eu && \
    echo "machine artifacts.bwell.com login $(cat /run/secrets/jfrog_user) password $(cat /run/secrets/jfrog_token)" > ~/.netrc && \
    chmod 600 ~/.netrc && \
    pipenv sync --dev --system && \
    rm -f ~/.netrc

# Copy the rest of the project files
COPY . /src

# Creating and switching to non root user
RUN addgroup -g 1001 nonrootgroup && \
    adduser -u 1001 -G nonrootgroup -s /bin/sh -D nonrootuser

USER nonrootuser
