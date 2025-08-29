# Pre-commit Hooks Documentation

## Overview

This project uses pre-commit hooks to maintain code quality and consistency. The hooks automatically format code, run linters, and perform various checks before commits are made.

## Installed Hooks

### On Every Commit
- **Ruff Format** - Code formatting (line length: 120)
- **Ruff** - Fast Python linter with auto-fix capabilities
- **File Checks**:
  - Remove trailing whitespace
  - Fix end-of-file newlines
  - Validate YAML files
  - Validate TOML files
  - Check for merge conflicts
  - Prevent large files from being committed
  - Check for debug statements
  - Normalize line endings to LF

### On Git Push
- **Pytest** - Run all unit tests

## Installation

### Quick Setup
```bash
# Run the setup script
./scripts/setup-pre-commit.sh
```

### Manual Setup
```bash
# Install development dependencies
uv pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install

# Install pre-push hooks
pre-commit install --hook-type pre-push

# Run hooks on all files (initial formatting)
pre-commit run --all-files
```

### Using Make Commands
```bash
# Install everything including pre-commit hooks
make install-dev
make install-pre-commit

# Format all code
make format

# Run all pre-commit hooks manually
make pre-commit
```

## Usage

### Automatic Execution
Hooks run automatically when you:
- `git commit` - Runs formatting and linting hooks
- `git push` - Runs test suite

### Manual Execution
```bash
# Run all hooks on all files
make pre-commit
# or
pre-commit run --all-files

# Run specific hook
pre-commit run ruff-format --all-files
pre-commit run ruff --all-files

# Run hooks on staged files only
pre-commit run

# Update hooks to latest versions
make pre-commit-update
# or
pre-commit autoupdate
```

### Bypassing Hooks (Use Sparingly!)
```bash
# Skip pre-commit hooks
git commit --no-verify -m "Emergency fix"

# Skip pre-push hooks
git push --no-verify
```

## Configuration

### Ruff Configuration (`pyproject.toml`)
```toml
[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
]

[tool.ruff.format]
# Ruff's formatter configuration
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "lf"
```

## Troubleshooting

### Common Issues

#### 1. Pre-commit not found
```bash
# Ensure you've installed dev dependencies
uv pip install -e ".[dev,test]"
```

#### 2. Hooks not running automatically
```bash
# Reinstall hooks
pre-commit install
pre-commit install --hook-type pre-push
```

#### 3. Formatting and Linting
Ruff handles both formatting and linting. The formatter runs first, then the linter with auto-fix capabilities.

#### 4. Tests failing on push
Tests run on push to prevent broken code from being pushed. If tests are failing:
- Fix the tests before pushing
- Or temporarily skip with `git push --no-verify` (not recommended)

#### 5. Large file warning
Pre-commit prevents accidentally committing large files (>500KB by default). If you need to commit a large file:
- Consider if it really needs to be in version control
- Use Git LFS for large binary files
- Or add to `.gitignore` if appropriate

### Gradual Adoption

The configuration allows for gradual adoption:
- Ruff is set to `fail_fast: false` to allow commits with some linting issues
- Tests only run on push, not on every commit
- You can fix issues incrementally

## CI Integration

The project includes GitHub Actions workflow (`.github/workflows/ci.yml`) that runs the same checks in CI:
- Pre-commit hooks on all files
- Full test suite with coverage
- Type checking with mypy

## Maintenance

### Updating Hook Versions
```bash
# Update all hooks to latest versions
make pre-commit-update

# Update specific hook
# Edit .pre-commit-config.yaml and change the 'rev' field
```

### Adding New Hooks
Edit `.pre-commit-config.yaml` and add new hook configurations. See [pre-commit.com](https://pre-commit.com/hooks.html) for available hooks.

### Modifying Rules
- Ruff formatting: Edit `[tool.ruff.format]` in `pyproject.toml`
- Ruff linting: Edit `[tool.ruff.lint]` in `pyproject.toml`
- Pre-commit hooks: Edit `.pre-commit-config.yaml`

## Benefits

1. **Consistent Code Style** - All code follows the same formatting rules
2. **Catch Issues Early** - Problems are found before code review
3. **Automated Fixes** - Many issues are automatically corrected
4. **Save CI Time** - Catch issues locally before pushing
5. **Better Code Quality** - Enforces best practices and prevents common mistakes

## Additional Resources

- [Pre-commit Documentation](https://pre-commit.com/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Ruff Formatter Documentation](https://docs.astral.sh/ruff/formatter/)
- [Project Makefile](../Makefile) - See all available commands
