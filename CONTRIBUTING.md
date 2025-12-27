# Contributing to Smart Home Assistant

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/smarthome.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Submit a pull request

## Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install pytest pytest-cov pytest-mock ruff pre-commit

# Install pre-commit hooks
pre-commit install

# Copy environment configuration
cp .env.example .env
# Edit .env with test/development credentials
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
ruff check src/ tools/

# Auto-fix issues
ruff check --fix src/ tools/

# Format code
ruff format src/ tools/
```

### Style Guidelines

- Use descriptive variable names (no single-letter variables)
- Add docstrings to public functions and classes
- Keep functions focused and small
- Use type hints for function signatures
- Follow existing code patterns

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_your_feature.py -v

# Run tests matching a pattern
pytest tests/ -k "test_pattern" -v
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names: `test_feature_when_condition_should_result`
- Use fixtures for common setup
- Mock external dependencies (API calls, database, etc.)

### Test-Driven Development (TDD)

We encourage TDD:

1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green

## Pull Request Process

### Before Submitting

1. Run all tests: `pytest tests/ -v`
2. Run linter: `ruff check src/ tools/`
3. Update documentation if needed
4. Add tests for new functionality
5. Update CHANGELOG.md if applicable

### PR Guidelines

- Use a clear, descriptive title
- Reference any related issues
- Describe what changes you made and why
- Include screenshots for UI changes
- Keep PRs focused on a single feature/fix

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests passing

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed my code
- [ ] Commented complex code
- [ ] Updated documentation
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(lights): add support for color temperature
fix(spotify): handle expired token gracefully
docs: update installation instructions
test(ha_client): add connection retry tests
```

## Architecture Decisions

For significant changes, please:

1. Discuss in an issue first
2. Document your approach
3. Consider backwards compatibility
4. Update ARCHITECTURE.md if needed

## Adding New Device Support

To add support for a new device type:

1. Create a new tool in `tools/`:
   ```python
   # tools/your_device.py
   def get_tool_definitions():
       return [{"name": "...", "description": "...", ...}]

   def handle_tool_call(name, arguments, ha_client):
       ...
   ```

2. Register in `tools/__init__.py`

3. Add tests in `tests/unit/test_your_device.py`

4. Update documentation

## Reporting Bugs

Include:
- Python version
- OS and version
- Home Assistant version
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output

## Feature Requests

Include:
- Use case description
- Expected behavior
- Any implementation ideas
- Impact on existing functionality

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Assume good intentions

## Questions?

Feel free to open an issue for any questions about contributing.
