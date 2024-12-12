FROM public.ecr.aws/docker/library/python:3.12-alpine3.20

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
RUN pipenv sync --dev --system

# Copy the rest of the project files
COPY . /src
