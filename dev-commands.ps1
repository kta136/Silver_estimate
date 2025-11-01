# Development Commands for SilverEstimate
# Usage: .\dev-commands.ps1 <command>
# Example: .\dev-commands.ps1 format

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host @"
SilverEstimate Development Commands
====================================

Code Formatting:
  format          Run Black and isort to auto-format code
  check-format    Check formatting without making changes

Code Quality:
  lint            Run flake8 and pylint
  type-check      Run mypy type checker
  quality         Run all quality checks (format check + lint + type check)

Testing:
  test            Run all tests with coverage
  test-fast       Run tests without coverage
  test-unit       Run only unit tests
  test-integration Run only integration tests

Pre-commit:
  hooks-install   Install pre-commit hooks
  hooks-run       Run pre-commit hooks on all files
  hooks-update    Update pre-commit hooks to latest versions

Build:
  build           Build executable with PyInstaller
  build-clean     Clean build artifacts before building

Security:
  security        Run security checks (Bandit + Safety)

Cleanup:
  clean           Remove build artifacts and cache files
  clean-all       Remove all generated files including venv

Setup:
  install         Install package in development mode
  install-dev     Install with all development dependencies

All:
  all             Run format, quality checks, and tests

Examples:
  .\dev-commands.ps1 format
  .\dev-commands.ps1 test
  .\dev-commands.ps1 quality
"@
}

function Invoke-Format {
    Write-Host "Running Black formatter..." -ForegroundColor Cyan
    black silverestimate tests
    Write-Host "Running isort..." -ForegroundColor Cyan
    isort silverestimate tests
    Write-Host "Formatting complete!" -ForegroundColor Green
}

function Invoke-CheckFormat {
    Write-Host "Checking Black formatting..." -ForegroundColor Cyan
    black --check --diff silverestimate tests
    Write-Host "Checking isort..." -ForegroundColor Cyan
    isort --check-only --diff silverestimate tests
    Write-Host "Format check complete!" -ForegroundColor Green
}

function Invoke-Lint {
    Write-Host "Running flake8..." -ForegroundColor Cyan
    flake8 silverestimate
    Write-Host "Running pylint..." -ForegroundColor Cyan
    pylint silverestimate --rcfile=pyproject.toml
    Write-Host "Linting complete!" -ForegroundColor Green
}

function Invoke-TypeCheck {
    Write-Host "Running mypy type checker..." -ForegroundColor Cyan
    mypy silverestimate --config-file=pyproject.toml
    Write-Host "Type check complete!" -ForegroundColor Green
}

function Invoke-Quality {
    Write-Host "Running all quality checks..." -ForegroundColor Cyan
    Invoke-CheckFormat
    Invoke-Lint
    Invoke-TypeCheck
    Write-Host "All quality checks complete!" -ForegroundColor Green
}

function Invoke-Test {
    Write-Host "Running tests with coverage..." -ForegroundColor Cyan
    pytest --cov --cov-report=html --cov-report=term-missing -v
    Write-Host "Tests complete! Coverage report: htmlcov/index.html" -ForegroundColor Green
}

function Invoke-TestFast {
    Write-Host "Running tests without coverage..." -ForegroundColor Cyan
    pytest -v
    Write-Host "Tests complete!" -ForegroundColor Green
}

function Invoke-TestUnit {
    Write-Host "Running unit tests..." -ForegroundColor Cyan
    pytest tests/unit -v
    Write-Host "Unit tests complete!" -ForegroundColor Green
}

function Invoke-TestIntegration {
    Write-Host "Running integration tests..." -ForegroundColor Cyan
    pytest tests/integration -v
    Write-Host "Integration tests complete!" -ForegroundColor Green
}

function Invoke-HooksInstall {
    Write-Host "Installing pre-commit hooks..." -ForegroundColor Cyan
    pre-commit install
    Write-Host "Pre-commit hooks installed!" -ForegroundColor Green
}

function Invoke-HooksRun {
    Write-Host "Running pre-commit hooks on all files..." -ForegroundColor Cyan
    pre-commit run --all-files
    Write-Host "Pre-commit hooks complete!" -ForegroundColor Green
}

function Invoke-HooksUpdate {
    Write-Host "Updating pre-commit hooks..." -ForegroundColor Cyan
    pre-commit autoupdate
    Write-Host "Pre-commit hooks updated!" -ForegroundColor Green
}

function Invoke-Build {
    Write-Host "Building executable with PyInstaller..." -ForegroundColor Cyan
    pyinstaller SilverEstimate.spec --noconfirm --log-level=INFO
    if (Test-Path "dist/SilverEstimate/SilverEstimate.exe") {
        Write-Host "Build complete! Executable: dist/SilverEstimate/SilverEstimate.exe" -ForegroundColor Green
        Get-Item "dist/SilverEstimate/SilverEstimate.exe" | Select-Object Name, Length, LastWriteTime
    } else {
        Write-Error "Build failed! Executable not found."
    }
}

function Invoke-BuildClean {
    Write-Host "Cleaning build artifacts..." -ForegroundColor Cyan
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    Write-Host "Build artifacts cleaned!" -ForegroundColor Green
    Invoke-Build
}

function Invoke-Security {
    Write-Host "Running Bandit security checks..." -ForegroundColor Cyan
    bandit -c pyproject.toml -r silverestimate
    Write-Host "Running Safety vulnerability checks..." -ForegroundColor Cyan
    safety check --json
    Write-Host "Security checks complete!" -ForegroundColor Green
}

function Invoke-Clean {
    Write-Host "Cleaning build artifacts and cache files..." -ForegroundColor Cyan

    # Python cache
    Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
    Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
    Get-ChildItem -Recurse -Filter "*.pyo" | Remove-Item -Force

    # Build artifacts
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "*.egg-info") { Remove-Item -Recurse -Force "*.egg-info" }

    # Test/coverage artifacts
    if (Test-Path ".pytest_cache") { Remove-Item -Recurse -Force ".pytest_cache" }
    if (Test-Path ".coverage") { Remove-Item -Force ".coverage" }
    if (Test-Path "htmlcov") { Remove-Item -Recurse -Force "htmlcov" }
    if (Test-Path "coverage.xml") { Remove-Item -Force "coverage.xml" }

    # Type checker cache
    if (Test-Path ".mypy_cache") { Remove-Item -Recurse -Force ".mypy_cache" }

    Write-Host "Cleanup complete!" -ForegroundColor Green
}

function Invoke-CleanAll {
    Invoke-Clean
    Write-Host "Removing virtual environment..." -ForegroundColor Cyan
    if (Test-Path ".venv") { Remove-Item -Recurse -Force ".venv" }
    Write-Host "All cleaned!" -ForegroundColor Green
}

function Invoke-Install {
    Write-Host "Installing package in development mode..." -ForegroundColor Cyan
    pip install -e .
    Write-Host "Installation complete!" -ForegroundColor Green
}

function Invoke-InstallDev {
    Write-Host "Installing package with development dependencies..." -ForegroundColor Cyan
    pip install -e ".[dev]"
    Write-Host "Installation complete!" -ForegroundColor Green
}

function Invoke-All {
    Write-Host "Running all checks..." -ForegroundColor Cyan
    Invoke-Format
    Invoke-Quality
    Invoke-Test
    Write-Host "All checks complete!" -ForegroundColor Green
}

# Command dispatcher
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "format" { Invoke-Format }
    "check-format" { Invoke-CheckFormat }
    "lint" { Invoke-Lint }
    "type-check" { Invoke-TypeCheck }
    "quality" { Invoke-Quality }
    "test" { Invoke-Test }
    "test-fast" { Invoke-TestFast }
    "test-unit" { Invoke-TestUnit }
    "test-integration" { Invoke-TestIntegration }
    "hooks-install" { Invoke-HooksInstall }
    "hooks-run" { Invoke-HooksRun }
    "hooks-update" { Invoke-HooksUpdate }
    "build" { Invoke-Build }
    "build-clean" { Invoke-BuildClean }
    "security" { Invoke-Security }
    "clean" { Invoke-Clean }
    "clean-all" { Invoke-CleanAll }
    "install" { Invoke-Install }
    "install-dev" { Invoke-InstallDev }
    "all" { Invoke-All }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}
