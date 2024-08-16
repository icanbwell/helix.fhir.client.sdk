FROM python:3.12-slim

COPY Pipfile* ./

RUN apt-get update && \
    apt-get install -y git && \
    pip install pipenv && \
    pipenv sync --dev --system

WORKDIR /sourcecode
RUN git config --global --add safe.directory /sourcecode
CMD ["pre-commit", "run", "--all-files"]
