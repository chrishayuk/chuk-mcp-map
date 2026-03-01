.PHONY: clean clean-pyc clean-build clean-test clean-all test run build publish publish-test publish-manual help install dev-install version bump-patch bump-minor bump-major release

# Default target
help:
	@echo "Available targets:"
	@echo "  clean          - Remove Python bytecode and basic artifacts"
	@echo "  clean-all      - Deep clean everything (pyc, build, test, cache)"
	@echo "  install        - Install package in current environment"
	@echo "  dev-install    - Install package in development mode"
	@echo "  test           - Run tests"
	@echo "  test-cov       - Run tests with coverage report"
	@echo "  lint           - Run code linters"
	@echo "  format         - Auto-format code"
	@echo "  typecheck      - Run type checking"
	@echo "  security       - Run security checks"
	@echo "  check          - Run all checks (lint, typecheck, security, test)"
	@echo "  run            - Run the MCP server"
	@echo "  build          - Build the project"
	@echo "  docker-build   - Build Docker image"
	@echo "  docker-run     - Run Docker container"
	@echo "  publish        - Tag and push to trigger GitHub Actions release"
	@echo "  publish-test   - Upload to TestPyPI for testing"
	@echo "  publish-manual - Manually upload to PyPI (requires PYPI_TOKEN)"
	@echo "  release        - Alias for publish"

# Basic clean
clean: clean-pyc clean-build
	@echo "Basic clean complete."

clean-pyc:
	@echo "Cleaning Python bytecode files..."
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@find . -type f -name '*.pyo' -delete 2>/dev/null || true
	@find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

clean-build:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info 2>/dev/null || true
	@rm -rf .eggs/ 2>/dev/null || true
	@find . -name '*.egg' -exec rm -f {} + 2>/dev/null || true

clean-test:
	@echo "Cleaning test artifacts..."
	@rm -rf .pytest_cache/ .coverage htmlcov/ .tox/ .cache/ 2>/dev/null || true
	@find . -name '.coverage.*' -delete 2>/dev/null || true

clean-all: clean-pyc clean-build clean-test
	@echo "Deep cleaning..."
	@rm -rf .mypy_cache/ .ruff_cache/ .uv/ node_modules/ 2>/dev/null || true
	@find . -name '.DS_Store' -delete 2>/dev/null || true
	@echo "Deep clean complete."

install:
	@if command -v uv >/dev/null 2>&1; then \
		echo "Installing with uv..."; \
		uv pip install .; \
	else \
		echo "Installing with pip..."; \
		pip install .; \
	fi

dev-install:
	@if command -v uv >/dev/null 2>&1; then \
		echo "Installing in editable mode with dev dependencies (using uv)..."; \
		uv pip install -e ".[dev]"; \
	else \
		echo "Installing in editable mode with dev dependencies (using pip)..."; \
		pip install -e ".[dev]"; \
	fi

test:
	@echo "Running tests..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run pytest; \
	elif command -v pytest >/dev/null 2>&1; then \
		pytest; \
	else \
		python -m pytest; \
	fi

test-cov coverage:
	@echo "Running tests with coverage..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run pytest --cov=src --cov-report=html --cov-report=term --cov-report=term-missing:skip-covered; \
		echo ""; \
		echo "=========================="; \
		echo "Coverage Summary:"; \
		echo "=========================="; \
		uv run coverage report --omit="tests/*" | tail -5; \
		echo ""; \
		echo "HTML coverage report saved to: htmlcov/index.html"; \
	else \
		pytest --cov=src --cov-report=html --cov-report=term --cov-report=term-missing:skip-covered; \
	fi

coverage-report:
	@echo "Coverage Report:"
	@if command -v uv >/dev/null 2>&1; then \
		uv run coverage report --omit="tests/*" || echo "No coverage data found. Run 'make test-cov' first."; \
	else \
		coverage report --omit="tests/*" || echo "No coverage data found. Run 'make test-cov' first."; \
	fi

run:
	@echo "Running Map MCP server..."
	@if command -v uv >/dev/null 2>&1; then \
		PYTHONPATH=src uv run python -m chuk_mcp_map.server; \
	else \
		PYTHONPATH=src python3 -m chuk_mcp_map.server; \
	fi

build: clean-build
	@echo "Building project..."
	@if command -v uv >/dev/null 2>&1; then \
		uv build; \
	else \
		python3 -m build; \
	fi
	@echo "Build complete."

docker-build:
	@echo "Building Docker image..."
	docker build -t chuk-mcp-map:latest .
	@echo "Docker image built: chuk-mcp-map:latest"

docker-run:
	@echo "Running Docker container..."
	docker run --rm -p 8000:8000 chuk-mcp-map:latest

version:
	@version=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	echo "Current version: $$version"

bump-patch:
	@current=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	patch=$$(echo $$current | cut -d. -f3); \
	new_patch=$$(($$patch + 1)); \
	new_version="$$major.$$minor.$$new_patch"; \
	sed -i.bak "s/^version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped: $$current -> $$new_version"

bump-minor:
	@current=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	new_minor=$$(($$minor + 1)); \
	new_version="$$major.$$new_minor.0"; \
	sed -i.bak "s/^version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped: $$current -> $$new_version"

bump-major:
	@current=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	major=$$(echo $$current | cut -d. -f1); \
	new_major=$$(($$major + 1)); \
	new_version="$$new_major.0.0"; \
	sed -i.bak "s/^version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped: $$current -> $$new_version"

publish:
	@version=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	tag="v$$version"; \
	echo "Creating tag $$tag..."; \
	git tag -a "$$tag" -m "Release $$tag" && \
	git push origin "$$tag" && \
	echo "Tag pushed. GitHub Actions will handle the release."

publish-test: build
	@echo "Publishing to TestPyPI..."
	@echo ""
	@version=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	echo "Version: $$version"; \
	echo ""; \
	if command -v uv >/dev/null 2>&1; then \
		uv run twine upload --repository testpypi dist/*; \
	else \
		python3 -m twine upload --repository testpypi dist/*; \
	fi; \
	echo ""; \
	echo "Uploaded to TestPyPI!"; \
	echo ""; \
	echo "Install with:"; \
	echo "  pip install --index-url https://test.pypi.org/simple/ chuk-mcp-map==$$version"

publish-manual: build
	@echo "Manual PyPI Publishing"
	@echo "======================"
	@echo ""
	@version=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	tag="v$$version"; \
	echo "Version: $$version"; \
	echo "Tag: $$tag"; \
	echo ""; \
	\
	echo "Pre-flight checks:"; \
	echo "=================="; \
	\
	if git diff --quiet && git diff --cached --quiet; then \
		echo "Working directory is clean"; \
	else \
		echo "Working directory has uncommitted changes"; \
		echo ""; \
		git status --short; \
		echo ""; \
		echo "Please commit or stash your changes before publishing."; \
		exit 1; \
	fi; \
	\
	if git tag -l | grep -q "^$$tag$$"; then \
		echo "Tag $$tag exists"; \
	else \
		echo "Tag $$tag does not exist yet"; \
		echo ""; \
		read -p "Create tag now? (y/N) " -n 1 -r; \
		echo ""; \
		if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
			git tag -a "$$tag" -m "Release $$tag"; \
			echo "Tag created locally"; \
		else \
			echo "Continuing without creating tag..."; \
		fi; \
	fi; \
	\
	echo ""; \
	echo "This will upload version $$version to PyPI"; \
	echo ""; \
	read -p "Continue? (y/N) " -n 1 -r; \
	echo ""; \
	if [[ ! $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Aborted."; \
		exit 1; \
	fi; \
	\
	echo ""; \
	echo "Uploading to PyPI..."; \
	if [ -n "$$PYPI_TOKEN" ]; then \
		if command -v uv >/dev/null 2>&1; then \
			uv run twine upload --username __token__ --password "$$PYPI_TOKEN" dist/*; \
		else \
			python3 -m twine upload --username __token__ --password "$$PYPI_TOKEN" dist/*; \
		fi; \
	else \
		if command -v uv >/dev/null 2>&1; then \
			uv run twine upload dist/*; \
		else \
			python3 -m twine upload dist/*; \
		fi; \
	fi; \
	echo ""; \
	echo "Published to PyPI!"; \
	echo ""; \
	if git tag -l | grep -q "^$$tag$$"; then \
		echo "Push tag with: git push origin $$tag"; \
	fi; \
	echo "Install with: pip install chuk-mcp-map==$$version"

release: publish

lint:
	@echo "Running linters..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff check .; \
		uv run ruff format --check .; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check .; \
		ruff format --check .; \
	else \
		echo "Ruff not found. Install with: pip install ruff"; \
	fi

format:
	@echo "Formatting code..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff format .; \
		uv run ruff check --fix .; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff format .; \
		ruff check --fix .; \
	else \
		echo "Ruff not found. Install with: pip install ruff"; \
	fi

typecheck:
	@echo "Running type checker..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run mypy src; \
	elif command -v mypy >/dev/null 2>&1; then \
		mypy src; \
	else \
		echo "MyPy not found. Install with: pip install mypy"; \
	fi

security:
	@echo "Running security checks..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run bandit -r src -ll; \
	elif command -v bandit >/dev/null 2>&1; then \
		bandit -r src -ll; \
	else \
		echo "Bandit not found. Install with: pip install bandit"; \
	fi

check: lint typecheck security test
	@echo "All checks completed."
