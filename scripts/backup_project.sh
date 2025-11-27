#!/bin/bash
set -e

# Configuration
PROJECT_NAME="market-prediction-app"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="../backups"
BACKUP_FILE="${BACKUP_DIR}/${PROJECT_NAME}_${TIMESTAMP}.zip"

# Create backups directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "Backing up project to $BACKUP_FILE"
echo "=========================================="

# Create zip file excluding heavy/unnecessary folders
# -x excludes files matching the pattern
zip -r "$BACKUP_FILE" . \
    -x "frontend/node_modules/*" \
    -x "*/node_modules/*" \
    -x ".venv/*" \
    -x "*/.venv/*" \
    -x "*/venv/*" \
    -x "*/env/*" \
    -x "*/__pycache__/*" \
    -x "*.DS_Store" \
    -x ".git/*" \
    -x "frontend/build/*" \
    -x "frontend/dist/*" \
    -x "*.pyc" \
    -x ".idea/*" \
    -x ".vscode/*" \
    -x "*/.pytest_cache/*" \
    -x "*/.mypy_cache/*" \
    -x "*/.coverage" \
    -x "*/htmlcov/*" \
    -x "*.egg-info/*" \
    -x "*/dist/*" \
    -x "*/build/*" \
    -x "_archive/*" \
    -x "*/site-packages/*" \
    -x "*/*/package/*" \ 

echo ""
echo "=========================================="
echo "✅ Backup Complete!"
echo "=========================================="
echo "File: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo ""
