# Contributing to S3verless

Thank you for your interest in contributing to S3verless! This document provides guidelines and instructions for contributing.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- uv (recommended) or pip
- Git
- AWS account (or LocalStack for local development)

### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/alexjacobs08/s3verless.git
   cd s3verless
   ```

2. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**:
   ```bash
   uv sync --all-extras
   ```

4. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate  # On Unix/macOS
   # or
   .venv\Scripts\activate  # On Windows
   ```

5. **Run tests to verify setup**:
   ```bash
   uv run pytest
   ```

## Development Workflow

### Making Changes

1. **Create a new branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our code style guidelines

3. **Run tests**:
   ```bash
   uv run pytest
   ```

4. **Format and lint your code**:
   ```bash
   # Format code with ruff
   uv run ruff format .
   
   # Check and fix linting issues
   uv run ruff check --fix .
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

6. **Push and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

We use **Ruff** for both linting and formatting:

### Formatting
```bash
# Format all files
uv run ruff format .

# Check formatting without making changes
uv run ruff format --check .
```

### Linting
```bash
# Check for linting issues
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .
```

### Type Checking
```bash
# Run mypy for type checking
uv run mypy s3verless
```

### Code Style Guidelines

- **Line length**: 88 characters
- **Type hints**: Use modern Python 3.9+ syntax (`str | None` instead of `Optional[str]`)
- **Imports**: 
  - Use absolute imports
  - Ruff will automatically sort and organize imports
- **Docstrings**: Use Google-style docstrings for all public functions/classes
- **Naming**: 
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_CASE`

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=s3verless --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_base.py

# Run specific test
uv run pytest tests/test_base.py::test_model_creation

# Run with verbose output
uv run pytest -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names that explain what is being tested
- Use fixtures from `tests/conftest.py` for common setup
- Aim for high test coverage (70%+ minimum)

Example test:
```python
import pytest
from s3verless import BaseS3Model

def test_model_creation():
    """Test that a basic model can be created."""
    class TestModel(BaseS3Model):
        name: str
        value: int
    
    instance = TestModel(name="test", value=42)
    assert instance.name == "test"
    assert instance.value == 42
```

For async tests:
```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations."""
    result = await some_async_function()
    assert result is not None
```

## Pull Request Guidelines

### Before Submitting

- [ ] Tests pass (`uv run pytest`)
- [ ] Code is formatted (`uv run ruff format .`)
- [ ] No linting errors (`uv run ruff check .`)
- [ ] Type checking passes (`uv run mypy s3verless`)
- [ ] Documentation is updated (if needed)
- [ ] CHANGELOG.md is updated (for significant changes)

### PR Description Template

```markdown
## Description
Brief description of what this PR does

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### Commit Message Guidelines

We follow conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

Examples:
```bash
feat: add query pagination support
fix: resolve S3 connection timeout issue
docs: update authentication example
test: add tests for unique field validation
```

## Project Structure

```
s3verless/
├── s3verless/           # Main package
│   ├── auth/           # Authentication module
│   ├── core/           # Core functionality
│   ├── fastapi/        # FastAPI integration
│   └── cli.py          # CLI tool
├── tests/              # Test suite
├── examples/           # Example applications
├── docs/               # Documentation
└── pyproject.toml      # Project configuration
```

## Adding New Features

### Adding a New Model Field Type

1. Update `BaseS3Model` if needed
2. Add validation logic
3. Update tests
4. Document in README

### Adding a New Query Feature

1. Update `S3Query` class
2. Add tests in `tests/test_query.py`
3. Update query documentation
4. Add example usage

### Adding a New API Endpoint

1. Update router generator or create custom router
2. Add tests in `tests/test_integration.py`
3. Document in API reference
4. Add to example applications

## Documentation

- Update README.md for user-facing changes
- Update docstrings for code changes
- Add examples for new features
- Update CHANGELOG.md for significant changes

## Release Process

(For maintainers)

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag: `git tag v0.x.x`
4. Build: `uv build`
5. Publish: `uv publish` (or `twine upload dist/*`)

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email alex.jacobs08+s3verless@gmail.com

## Development Tips

### Using LocalStack

For local S3 development without AWS:

```bash
# Start LocalStack
docker run -d -p 4566:4566 localstack/localstack

# Set environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

### Useful Commands

```bash
# Install package in development mode
uv pip install -e .

# Run specific test with output
uv run pytest -s tests/test_base.py::test_model_creation

# Check test coverage for specific module
uv run pytest --cov=s3verless.core --cov-report=html

# Run linter on specific file
uv run ruff check s3verless/core/base.py

# Format specific file
uv run ruff format s3verless/core/base.py
```

## Common Issues

### Import Errors
Make sure you've installed the package in development mode and activated the virtual environment.

### Test Failures
Check that you're using the correct Python version (3.9+) and that all dependencies are installed.

### LocalStack Connection Issues
Ensure LocalStack is running and the AWS_URL environment variable is set correctly.

## License

By contributing to S3verless, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to S3verless! 🎉
