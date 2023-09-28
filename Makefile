LANG=en_US.utf-8

export LANG

Pipfile.lock: Pipfile
	docker compose run --rm --name helix.fhir.client.sdk dev pipenv lock --dev

.PHONY:devdocker
devdocker: ## Builds the docker for dev
	docker compose build

.PHONY:init
init: devdocker up setup-pre-commit  ## Initializes the local developer environment

.PHONY: up
up: Pipfile.lock
	docker compose up --build -d --remove-orphans && \
	echo "\nwaiting for Mongo server to become healthy" && \
	while [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk-mongo-1`" != "healthy" ] && [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk-mongo-1`" != "unhealthy" ] && [ "`docker inspect --format {{.State.Status}} helixfhirclientsdk-mongo-1`" != "restarting" ]; do printf "." && sleep 2; done && \
	if [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk-mongo-1`" != "healthy" ]; then docker ps && docker logs helixfhirclientsdk-mongo-1 && printf "========== ERROR: helixfhirclientsdk-mongo-1 did not start. Run docker logs helixfhirclientsdk-mongo-1 =========\n" && exit 1; fi
	echo "\nwaiting for FHIR server to become healthy" && \
	while [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk-fhir-1`" != "healthy" ] && [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk-fhir-1`" != "unhealthy" ] && [ "`docker inspect --format {{.State.Status}} helixfhirclientsdk-fhir-1`" != "restarting" ]; do printf "." && sleep 2; done && \
	if [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk-fhir-1`" != "healthy" ]; then docker ps && docker logs helixfhirclientsdk-fhir-1 && printf "========== ERROR: helixfhirclientsdk-mongo-1 did not start. Run docker logs helixfhirclientsdk-fhir-1 =========\n" && exit 1; fi
	@echo MockServer dashboard: http://localhost:1080/mockserver/dashboard
	@echo Fhir server dashboard http://localhost:3000/

.PHONY: down
down:
	docker compose down

.PHONY:clean-pre-commit
clean-pre-commit: ## removes pre-commit hook
	rm -f .git/hooks/pre-commit

.PHONY:setup-pre-commit
setup-pre-commit: Pipfile.lock
	cp ./pre-commit-hook ./.git/hooks/pre-commit

.PHONY:run-pre-commit
run-pre-commit: setup-pre-commit
	./.git/hooks/pre-commit

.PHONY:update
update: down Pipfile.lock setup-pre-commit  ## Updates all the packages using Pipfile
	docker compose run --rm --name helix.fhir.client.sdk dev pipenv sync && \
	make devdocker && \
	make pipenv-setup

.PHONY:tests
tests: up
	docker compose run --rm --name helix.fhir.client.sdk dev pytest tests && \
	docker compose run --rm --name helix.fhir.client.sdk dev pytest tests_integration

.PHONY:tests_integration
tests_integration: up
	docker compose run --rm --name helix.fhir.client.sdk dev pytest tests_integration

.PHONY:shell
shell:devdocker ## Brings up the bash shell in dev docker
	docker compose run --rm --name helix.fhir.client.sdk dev /bin/bash

.PHONY:build
build:
	docker compose run --rm --name helix.fhir.client.sdk dev rm -rf dist/
	docker compose run --rm --name helix.fhir.client.sdk dev python3 setup.py sdist bdist_wheel

.PHONY:testpackage
testpackage:build
	docker compose run --rm --name helix.fhir.client.sdk dev python3 -m twine upload -u __token__ --repository testpypi dist/*
# password can be set in TWINE_PASSWORD. https://twine.readthedocs.io/en/latest/

.PHONY:package
package:build
	docker compose run --rm --name helix.fhir.client.sdk dev python3 -m twine upload -u __token__ --repository pypi dist/*
# password can be set in TWINE_PASSWORD. https://twine.readthedocs.io/en/latest/

.DEFAULT_GOAL := help
.PHONY: help
help: ## Show this help.
	# from https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: sphinx-html
sphinx-html: ## build documentation
	docker compose run --rm --name helix.fhir.client.sdk dev make -C docsrc html
	@echo "copy html to docs... why? https://github.com/sphinx-doc/sphinx/issues/3382#issuecomment-470772316"
	@rm -rf docs
	@mkdir docs
	@touch docs/.nojekyll
	cp -a docsrc/_build/html/. docs

console_test:  ## runs the test via console to download resources from FHIR server
	#source ~/.bash_profile
	python ./console_test.py

.PHONY:pipenv-setup
pipenv-setup:devdocker ## Brings up the bash shell in dev docker
	docker compose run --rm --name helix.fhir.client.sdk dev pipenv-setup sync --pipfile

.PHONY:clean
clean: down
	docker image rm imranq2/node-fhir-server-mongo -f
	docker image rm node-fhir-server-mongo_fhir -f
	docker volume rm helixfhirclientsdk_mongo_data -f
ifneq ($(shell docker volume ls | grep "helixfhirclientsdk"| awk '{print $$2}'),)
	docker volume ls | grep "helixfhirclientsdk" | awk '{print $$2}' | xargs docker volume rm
endif


VENV_NAME=venv_fhir_client_sdk

.PHONY:venv
venv:
	python3 -m venv $(VENV_NAME)

.PHONY:devsetup
devsetup:venv
	source ./$(VENV_NAME)/bin/activate

.PHONY:show_dependency_graph
show_dependency_graph:
	docker compose run --rm --name helix.fhir.client.sdk dev sh -c "pipenv install --skip-lock && pipenv graph --reverse"
	docker compose run --rm --name helix.fhir.client.sdk dev sh -c "pipenv install -d && pipenv graph"

.PHONY:qodana
qodana:
	docker run --rm -it --name qodana --mount type=bind,source="$(pwd)",target=/data/project -p 8080:8080 jetbrains/qodana-python:2023.2 --show-report

