#!/bin/bash
# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Path to virtual environment python
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    echo "Please run 'python3 -m venv .venv' in the project root and install requirements."
    exit 1
fi

# Run the monitor script
"$VENV_PYTHON" "$SCRIPT_DIR/monitor.py"
