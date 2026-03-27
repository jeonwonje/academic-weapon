#!/bin/bash
# Quick setup script for Canvas Auto-Sync

echo "🎯 Canvas Auto-Sync Setup"
echo "=========================="
echo ""

# Check if Python 3.11+ is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -e .

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your Canvas API token!"
    echo "   Get your token from: Canvas → Settings → + New Access Token"
fi

# Create directories
mkdir -p data logs

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your CANVAS_API_TOKEN"
echo "2. Run: source .venv/bin/activate"
echo "3. Run: python scripts/sync_canvas.py"
echo ""
