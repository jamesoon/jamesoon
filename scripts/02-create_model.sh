#!/bin/bash
# Script to create the ML model pickle file

echo "Creating ML model (model.pkl)..."
python ml_source/create_model.py

if [ $? -eq 0 ]; then
    echo "ML model created successfully: ml_source/model.pkl"
else
    echo "Error creating ML model."
    exit 1
fi
