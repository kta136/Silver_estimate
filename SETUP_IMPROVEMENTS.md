# Setup Guide for Project Improvements

This guide walks you through setting up the new development tools and configurations added to the SilverEstimate project.

## What Was Added

1. **pyproject.toml** - Modern Python packaging with tool configurations
2. **.pre-commit-config.yaml** - Automated code quality checks
3. **.github/workflows/pr-validation.yml** - CI/CD validation workflow
4. **Type hints** - Added to key repository methods

## Quick Start (5 minutes)

### Step 1: Install the Project in Development Mode

```powershell
# Ensure you're in the project root
cd d:\Projects\SilverEstimate

# Activate your virtual environment (if using one)
.\.venv\Scripts\Activate.ps1

# Install the project with development dependencies
pip install -e ".[dev]"
```

This will install all dependencies defined in `pyproject.toml`.

### Step 2: Set Up Pre-commit Hooks

```powershell
# Install pre-commit hooks
pre-commit install

# (Optional) Run on all files to see current status
pre-commit run --all-files
```

Now, every time you commit, the following will run automatically:
- Black (code formatter)
- isort (import sorter)
- flake8 (linter)
- mypy (type checker)
- Various file checks (trailing whitespace, merge conflicts, etc.)
- Bandit (security checks)

### Step 3: Test the CI Workflow

The PR validation workflow will run automatically on:
- Pull requests to master/main
- Pushes to master/main

You can test it locally by running the same commands:

```powershell
# Code formatting check
black --check silverestimate tests

# If you want to auto-format
black silverestimate tests

# Import sorting check
isort --check-only silverestimate tests

# If you want to auto-sort
isort silverestimate tests

# Linting
flake8 silverestimate

# Type checking
mypy silverestimate

# Run tests with coverage
pytest --cov
```

## Detailed Configuration

### pyproject.toml

This file now contains:
- Project metadata (name, version, dependencies)
- Tool configurations (black, isort, mypy, pytest, pylint, coverage)
- Build system configuration

**Key Benefits:**
- Single source of truth for project configuration
- Better dependency management
- IDE integration (VS Code, PyCharm)

### Pre-commit Hooks

The `.pre-commit-config.yaml` file defines hooks that run before each commit.

**To temporarily skip hooks** (not recommended):
```powershell
git commit --no-verify -m "Your message"
```

**To update hooks to latest versions**:
```powershell
pre-commit autoupdate
```

### CI/CD Workflow

The PR validation workflow runs 5 parallel jobs:

1. **Code Quality** - Black, isort, flake8, pylint
2. **Type Checking** - mypy
3. **Tests** - pytest on Python 3.11, 3.12, 3.13
4. **Security** - Bandit and safety checks
5. **Build Check** - Verify PyInstaller still works

## Migration Notes

### Version Management

The version is still in `app_constants.py` for now. To use the version from `pyproject.toml`:

```python
# In app_constants.py (future improvement)
from importlib.metadata import version
APP_VERSION = version("silverestimate")
```

This requires the package to be installed with `pip install -e .`

### Gradual Type Hint Adoption

Type hints have been added to `items_repository.py`. Continue adding them to other files:

**Priority order:**
1. Repository classes (persistence layer)
2. Service layer classes
3. Controller classes
4. UI layer (lowest priority due to PyQt5 complexity)

### Tool Configuration

All tool configs are in `pyproject.toml`. You can adjust them as needed:

- **Black**: Line length is 88 (default)
- **mypy**: Gradual typing mode (strict checks are commented out)
- **pytest**: Coverage minimum is 50% (increase gradually)

## Troubleshooting

### Pre-commit Hook Failures

If pre-commit hooks fail:

1. **Black/isort failures**: Let them auto-fix
   ```powershell
   black silverestimate tests
   isort silverestimate tests
   git add -u
   git commit -m "Your message"
   ```

2. **Flake8 failures**: Fix manually or suppress specific warnings
   ```python
   # noqa: E501  # Line too long
   ```

3. **Mypy failures**: Add type: ignore comments temporarily
   ```python
   result = some_function()  # type: ignore
   ```

### CI Workflow Failures

Check the GitHub Actions tab in your repository to see detailed logs.

Common issues:
- **Import errors**: Ensure all imports work on Windows
- **Test failures**: Run tests locally first with `pytest`
- **Build failures**: Test PyInstaller locally with the spec file

## Next Steps

### Immediate (This Week)

1. Run `pre-commit run --all-files` to see current code quality
2. Fix any critical issues flagged by the tools
3. Test a commit to ensure hooks work
4. Push to see CI workflow in action

### Short Term (This Month)

1. Add more type hints to repository classes
2. Increase test coverage to 60%+
3. Fix any security issues flagged by Bandit
4. Update dependencies to latest versions

### Long Term (This Quarter)

1. Enable strict type checking in mypy (`disallow_untyped_defs = true`)
2. Reach 80% test coverage
3. Add property-based tests with hypothesis
4. Generate API documentation with Sphinx

## Additional Resources

- [Black documentation](https://black.readthedocs.io/)
- [isort documentation](https://pycqa.github.io/isort/)
- [mypy documentation](https://mypy.readthedocs.io/)
- [pre-commit documentation](https://pre-commit.com/)
- [pytest documentation](https://docs.pytest.org/)

## Getting Help

If you encounter issues:

1. Check the tool's documentation
2. Review the GitHub Actions logs for CI failures
3. Consult the project's development team
4. Open an issue in the project repository

---

**Note**: These improvements are designed to be adopted gradually. Don't try to fix everything at once. Focus on new code first, then gradually improve existing code.
