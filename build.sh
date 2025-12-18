#!/bin/bash
set -e

echo "🚀 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo "✅ Dependencies installed."

echo "🚀 Starting the application..."
python main.py
