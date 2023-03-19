FROM python:3.7-slim-bullseye

COPY ${project_root}/Pipfile* ./
RUN apt-get update && \
    apt-get install -y git && \
    pip install pipenv && \
    pipenv sync --dev --system
WORKDIR /sourcecode
CMD git config --global --add safe.directory /sourcecode && git status && pre-commit run --all-files
