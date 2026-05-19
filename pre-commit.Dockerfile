FROM 856965016623.dkr.ecr.us-east-1.amazonaws.com/root-mirror/python:3.12-alpine3.20

# Install git, build-essential, and pipenv
RUN apk add --no-cache git build-base && \
    pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile* ./

# Install dependencies using pipenv
RUN --mount=type=secret,id=jfrog_user \
    --mount=type=secret,id=jfrog_token \
    set -eu && \
    echo "machine artifacts.bwell.com login $(cat /run/secrets/jfrog_user) password $(cat /run/secrets/jfrog_token)" > ~/.netrc && \
    chmod 600 ~/.netrc && \
    pipenv sync --dev --system && \
    rm -f ~/.netrc

# Set the working directory
WORKDIR /sourcecode

# Clean up unnecessary files
RUN git config --global --add safe.directory /sourcecode

# Creating and switching to non root user
RUN addgroup -g 1001 nonrootgroup && \
    adduser -u 1001 -G nonrootgroup -s /bin/sh -D nonrootuser

USER nonrootuser

# Define the command to run
CMD ["pre-commit", "run", "--all-files"]
