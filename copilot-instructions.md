# Copilot Instructions

This file provides guidelines and best practices for GitHub Copilot and other AI coding assistants when working in this repository.

## General Guidelines
- Follow the repository's coding standards and conventions.
- Write clear, concise, and well-documented code.
- Prefer early returns and flattened control flow to reduce deep nesting.
- Use type hints and docstrings for all public functions and methods.
- Write and update tests for all new features and bug fixes.
- Use existing libraries and utilities in the project when possible.
- Avoid introducing breaking changes unless explicitly required.
- Ensure all code passes linting and tests before submitting changes.

## File/Folder Structure
- Place new modules in the appropriate subdirectory under `fhirnotesvectorstore/`.
- Place new tests in the corresponding folder under `tests/`.
- Update `README.md` and other documentation as needed for new features.

## Commit Messages
- Use clear, descriptive commit messages that explain the purpose of the change.

## Pull Requests
- Reference related issues or feature requests in pull requests.
- Provide a summary of changes and any special instructions for reviewers.

## Special Instructions
- For embedding and FHIR-related code, follow the patterns established in the `fhir_notes` and `vectorsearch` modules.
- For Docker or deployment changes, update the relevant `docker-compose` and `Dockerfile` as needed.

---

_This file is intended for use by GitHub Copilot and other AI coding assistants to ensure consistency and quality in code contributions._

