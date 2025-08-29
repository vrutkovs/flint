.PHONY: help install install-dev install-pre-commit format lint test test-cov typecheck pre-commit clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies
	uv pip install -e .

install-dev: ## Install development dependencies
	uv pip install -e ".[dev,test]"

install-pre-commit: install-dev ## Install pre-commit hooks
	pre-commit install
	@echo "Pre-commit hooks installed successfully!"

format: ## Format code with ruff
	ruff check --fix src/ tests/
	ruff format src/ tests/

lint: ## Run linting checks with ruff
	ruff check src/ tests/

test: ## Run unit tests
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	pytest tests/ --cov=src --junitxml=junit.xml -o junit_family=legacy

typecheck: ## Run type checking with mypy
	mypy src/

pre-commit: ## Run all pre-commit hooks on all files
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks to latest versions
	pre-commit autoupdate

clean: ## Clean up cache and build files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true
	rm -rf build/ 2>/dev/null || true
	rm -rf *.egg-info 2>/dev/null || true
