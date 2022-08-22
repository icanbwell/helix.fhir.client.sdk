LANG=en_US.utf-8

export LANG

Pipfile.lock: Pipfile
	docker-compose run --rm --name helix.fhir.client.sdk dev pipenv lock --dev

.PHONY:devdocker
devdocker: ## Builds the docker for dev
	docker-compose build

.PHONY:init
init: devdocker up setup-pre-commit  ## Initializes the local developer environment

.PHONY: up
up: Pipfile.lock
	docker-compose up --build -d --remove-orphans && \
	echo "\nwaiting for Mongo server to become healthy" && \
	while [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk_mongo_1`" != "healthy" ] && [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk_mongo_1`" != "unhealthy" ] && [ "`docker inspect --format {{.State.Status}} helixfhirclientsdk_mongo_1`" != "restarting" ]; do printf "." && sleep 2; done && \
	if [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk_mongo_1`" != "healthy" ]; then docker ps && docker logs helixfhirclientsdk_mongo_1 && printf "========== ERROR: helixfhirclientsdk_mongo_1 did not start. Run docker logs helixfhirclientsdk_mongo_1 =========\n" && exit 1; fi
	echo "\nwaiting for FHIR server to become healthy" && \
	while [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk_fhir_1`" != "healthy" ] && [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk_fhir_1`" != "unhealthy" ] && [ "`docker inspect --format {{.State.Status}} helixfhirclientsdk_fhir_1`" != "restarting" ]; do printf "." && sleep 2; done && \
	if [ "`docker inspect --format {{.State.Health.Status}} helixfhirclientsdk_fhir_1`" != "healthy" ]; then docker ps && docker logs helixfhirclientsdk_fhir_1 && printf "========== ERROR: helixfhirclientsdk_mongo_1 did not start. Run docker logs helixfhirclientsdk_fhir_1 =========\n" && exit 1; fi
	@echo MockServer dashboard: http://localhost:1080/mockserver/dashboard

.PHONY: down
down:
	docker-compose down

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
	docker-compose run --rm --name helix.fhir.client.sdk dev pipenv sync && \
	make devdocker && \
	make pipenv-setup

.PHONY:tests
tests: up
	docker-compose run --rm --name helix.fhir.client.sdk dev pytest tests && \
	docker-compose run --rm --name helix.fhir.client.sdk dev pytest tests_integration

.PHONY:shell
shell:devdocker ## Brings up the bash shell in dev docker
	docker-compose run --rm --name helix.fhir.client.sdk dev /bin/bash

.PHONY:build
build:
	docker-compose run --rm --name helix.fhir.client.sdk dev rm -rf dist/
	docker-compose run --rm --name helix.fhir.client.sdk dev python3 setup.py sdist bdist_wheel

.PHONY:testpackage
testpackage:build
	docker-compose run --rm --name helix.fhir.client.sdk dev python3 -m twine upload -u __token__ --repository testpypi dist/*
# password can be set in TWINE_PASSWORD. https://twine.readthedocs.io/en/latest/

.PHONY:package
package:build
	docker-compose run --rm --name helix.fhir.client.sdk dev python3 -m twine upload -u __token__ --repository pypi dist/*
# password can be set in TWINE_PASSWORD. https://twine.readthedocs.io/en/latest/

.DEFAULT_GOAL := help
.PHONY: help
help: ## Show this help.
	# from https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: sphinx-html
sphinx-html: ## build documentation
	docker-compose run --rm --name helix.fhir.client.sdk dev make -C docsrc html
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
	docker-compose run --rm --name helix.fhir.client.sdk dev pipenv-setup sync --pipfile
