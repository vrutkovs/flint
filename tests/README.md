# Flint Bot - Unit Tests

This directory contains comprehensive unit tests for the Flint Telegram bot application.

## Test Structure

```
tests/
├── __init__.py           # Test package initialization
├── conftest.py           # Shared pytest fixtures and configuration
├── test_settings.py      # Tests for Settings class
├── test_telega.py        # Tests for main Telega bot class
├── test_photo.py         # Tests for photo processing plugin
└── test_schedule.py      # Tests for scheduling plugin
```

## Running Tests

### Prerequisites

First, install the test dependencies:

```bash
pip install -e ".[test]"
```

Or using uv:

```bash
uv pip install -e ".[test]"
```

### Run All Tests

```bash
pytest tests/ -v
```

Or using the project script:

```bash
python -m pytest tests/ -v
```

### Run Tests with Coverage

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

Or using the project script:

```bash
pytest tests/ --cov=src --cov-report=html
```

This will generate an HTML coverage report in `htmlcov/index.html`.

### Run Specific Test Files

```bash
# Test only settings
pytest tests/test_settings.py -v

# Test only the main Telega class
pytest tests/test_telega.py -v

# Test only photo plugin
pytest tests/test_photo.py -v
```

### Run Specific Test Classes or Methods

```bash
# Run a specific test class
pytest tests/test_settings.py::TestSettings -v

# Run a specific test method
pytest tests/test_settings.py::TestSettings::test_settings_initialization -v
```

### Run Tests with Different Verbosity Levels

```bash
# Quiet mode
pytest tests/ -q

# Verbose mode
pytest tests/ -v

# Very verbose mode (shows full diff on failures)
pytest tests/ -vv
```

### Run Tests in Parallel

If you have pytest-xdist installed:

```bash
pip install pytest-xdist
pytest tests/ -n auto
```

## Test Coverage Goals

The test suite aims to achieve:
- **Minimum 80% code coverage** for all modules
- **100% coverage** for critical paths (message handling, API interactions)
- **Edge case testing** for error conditions and exceptions

## Writing New Tests

### Test File Naming

- Test files should be named `test_<module_name>.py`
- Test classes should be named `Test<ClassName>`
- Test methods should be named `test_<method_name>_<scenario>`

### Using Fixtures

Common fixtures are defined in `conftest.py`:

```python
@pytest.fixture
def mock_settings():
    """Returns a mock Settings object."""
    ...

@pytest.fixture
def mock_telegram_update():
    """Returns a mock Telegram Update object."""
    ...

@pytest.fixture
def mock_genai_client():
    """Returns a mock GenAI client."""
    ...
```

### Example Test Structure

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestMyFeature:
    @pytest.fixture
    def setup_data(self):
        """Setup test data."""
        return {"key": "value"}

    def test_sync_method(self, setup_data):
        """Test synchronous method."""
        assert setup_data["key"] == "value"

    @pytest.mark.asyncio
    async def test_async_method(self):
        """Test asynchronous method."""
        result = await some_async_function()
        assert result is not None
```

## Continuous Integration

Tests are designed to run in CI/CD pipelines. Make sure to:

1. Keep tests isolated (no external dependencies)
2. Use mocks for all external services
3. Ensure tests are deterministic
4. Keep test execution time under 30 seconds total

## Mock Objects

The test suite extensively uses mocks to simulate:

- **Telegram API**: Bot, Update, Message, Context objects
- **Google GenAI**: Client and response objects
- **MCP Services**: Configuration and client objects
- **File I/O**: Image buffers and file operations
- **External APIs**: Weather, calendar, and other services

## Test Categories

### Unit Tests
- Test individual functions and methods in isolation
- Mock all dependencies
- Focus on logic and data transformation

### Integration Tests (Future)
- Test interaction between components
- Use real configurations with test data
- Verify end-to-end workflows

### Performance Tests (Future)
- Test response times
- Memory usage monitoring
- Concurrent request handling

## Debugging Failed Tests

### View Detailed Output

```bash
pytest tests/ -vv --tb=long
```

### Debug with pdb

```bash
pytest tests/ --pdb
```

This will drop into the Python debugger on test failure.

### Show Local Variables

```bash
pytest tests/ --showlocals
```

### Capture Output

```bash
# Show print statements
pytest tests/ -s

# Show both stdout and logging
pytest tests/ -s --log-cli-level=DEBUG
```

## Known Issues and Limitations

1. **Async Testing**: Some async tests may require specific event loop configurations
2. **Mock Complexity**: Deep mocking of Telegram objects can be complex
3. **External Service Mocks**: MCP service mocks may not fully replicate actual behavior

## Contributing

When adding new features:

1. Write tests FIRST (TDD approach recommended)
2. Ensure all new code has corresponding tests
3. Update this README if adding new test categories
4. Run the full test suite before submitting PR
5. Aim for >80% coverage on new code

## Test Dependencies

The test suite uses the following key packages:

- `pytest`: Core testing framework
- `pytest-asyncio`: Async test support
- `pytest-cov`: Coverage reporting
- `pytest-mock`: Enhanced mocking utilities
- `pytest-timeout`: Test timeout management
- `faker`: Test data generation

## Support

For questions about tests:
1. Check existing test examples
2. Review pytest documentation
3. Consult the main project README
4. Open an issue on GitHub
