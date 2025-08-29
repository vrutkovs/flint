#!/bin/bash

# Setup script for pre-commit hooks
# This script installs and configures pre-commit hooks for the Flint project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

echo "Setting up pre-commit hooks for Flint project..."
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install development dependencies
print_status "Installing development dependencies..."
uv pip install -e ".[dev,test]"

# Install pre-commit hooks
print_status "Installing pre-commit hooks..."
pre-commit install

# Install pre-push hooks for tests
print_status "Installing pre-push hooks..."
pre-commit install --hook-type pre-push

# Run pre-commit on all files to check current status
echo
print_status "Running initial code formatting..."
echo

# Run ruff format
if pre-commit run ruff-format --all-files; then
    print_status "Ruff formatting completed"
else
    print_warning "Ruff made some formatting changes"
fi

# Run ruff with auto-fix
if pre-commit run ruff --all-files; then
    print_status "Ruff linting completed"
else
    print_warning "Ruff found some issues (check output above)"
fi

# Run other hooks
if pre-commit run --all-files --hook-stage manual trailing-whitespace end-of-file-fixer check-yaml check-toml; then
    print_status "Other checks completed"
else
    print_warning "Some files were modified (check output above)"
fi

echo
print_status "Pre-commit hooks setup complete!"
echo
echo "The following hooks are now active:"
echo "  • Ruff format (code formatting) - runs on commit"
echo "  • Ruff (linting with auto-fix) - runs on commit"
echo "  • File checks (trailing whitespace, EOF, YAML/TOML validation) - runs on commit"
echo "  • Pytest (unit tests) - runs on push"
echo
echo "Usage:"
echo "  • Hooks will run automatically on 'git commit' and 'git push'"
echo "  • To run manually: 'make pre-commit' or 'pre-commit run --all-files'"
echo "  • To skip hooks temporarily: 'git commit --no-verify'"
echo "  • To update hooks: 'make pre-commit-update'"
echo
print_warning "Note: Some tests may be failing due to existing issues in the codebase."
print_warning "      You can commit with --no-verify if needed, but please fix tests soon."
