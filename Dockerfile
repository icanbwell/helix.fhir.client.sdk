FROM python:3.7-slim
# https://github.com/imranq2/docker.spark_python
USER root

RUN apt-get update && apt-get install make

COPY Pipfile* /src/
WORKDIR /src

RUN python -m pip install --no-cache-dir pipenv
RUN pipenv lock && pipenv sync --dev --system && pipenv-setup sync --pipfile

COPY . /src

# run pre-commit once so it installs all the hooks and subsequent runs are fast
#RUN cd /src && pre-commit install

# USER 1001
