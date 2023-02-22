FROM python:3.7-slim

COPY ${project_root}/Pipfile* ./
RUN apt-get update && \
    apt-get install -y git && \
    git config --global --add safe.directory /src && \
    pip install pipenv && \
    pipenv sync --dev --system
WORKDIR /sourcecode
CMD pre-commit run --all-files
