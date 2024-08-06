FROM python:3.10-slim-bookworm


COPY Pipfile* ./
RUN apt-get update && \
    apt-get install -y git && \
    pip install pipenv && \
    pipenv sync --dev --system
WORKDIR /sourcecode
CMD git config --global --add safe.directory /sourcecode && git status && pre-commit run --all-files
