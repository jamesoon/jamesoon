#!/bin/bash
set -e

echo "Running Ruff (Linting & Formatting)..."
ruff check .
ruff format --check .

echo "Running Pytest..."
pytest

echo "All checks passed!"
