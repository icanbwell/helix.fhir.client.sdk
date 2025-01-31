FROM public.ecr.aws/docker/library/python:3.12-alpine3.20

# Install git, build-essential, and pipenv
RUN apk add --no-cache git build-base && \
    pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile* ./

# Install dependencies using pipenv
RUN pipenv sync --dev --system

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
