FROM python:3.12-slim
USER root

RUN apt-get update && apt-get install make

COPY Pipfile* /src/
WORKDIR /src
#RUN apt-get install -y git && git --version && git config --global --add safe.directory /src

RUN python -m pip install --no-cache-dir pipenv
RUN pipenv sync --dev --system

COPY . /src

# run pre-commit once so it installs all the hooks and subsequent runs are fast
#RUN cd /src && pre-commit install

# USER 1001
