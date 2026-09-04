#!/bin/bash
# scripts/run_tests.sh - Test runner following repo venv convention

set -e

echo "🧪 Running VDMC Core Library Tests"

# Ensure we're in the right directory
cd "$(dirname "$0")/.."

# Check if we're in virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "📌 Activating virtual environment..."
    if [[ -f "../../../.venv/bin/activate" ]]; then
        source ../../../.venv/bin/activate
    elif [[ -f "../../.venv/bin/activate" ]]; then
        source ../../.venv/bin/activate
    else
        echo "❌ Virtual environment not found. Please run from project root."
        exit 1
    fi
fi

# Install dependencies if needed
echo "📦 Installing dependencies..."
poetry install --quiet

# Run linting and code quality checks
echo "📝 Running code quality checks..."
echo "  - Black formatting check..."
black --check vdmc_core tests benchmarks || {
    echo "❌ Code formatting issues found. Run: black vdmc_core tests benchmarks"
    exit 1
}

echo "  - Import sorting check..."
isort --check-only vdmc_core tests benchmarks || {
    echo "❌ Import sorting issues found. Run: isort vdmc_core tests benchmarks"
    exit 1
}

echo "  - Ruff linting..."
ruff check vdmc_core tests benchmarks || {
    echo "❌ Linting issues found. Run: ruff check --fix vdmc_core tests benchmarks"
    exit 1
}

echo "  - Type checking..."
mypy vdmc_core || {
    echo "❌ Type checking failed."
    exit 1
}

# Run unit tests with coverage
echo "🧪 Running unit tests..."
pytest tests/ \
    --cov=vdmc_core \
    --cov-report=term-missing \
    --cov-fail-under=90 \
    --verbose || {
    echo "❌ Unit tests failed."
    exit 1
}

# Run performance benchmarks
echo "⚡ Running performance benchmarks..."
pytest benchmarks/ -m benchmark --verbose || {
    echo "❌ Performance benchmarks failed."
    exit 1
}

echo "✅ All tests passed!"
echo "📊 VDMC Core Library is ready for integration!" 