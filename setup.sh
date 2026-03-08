#!/bin/bash
set -e

echo "=== CrowdLens Setup ==="
echo ""

# Create required directories
mkdir -p videos data

# Backend setup
echo "Setting up backend..."
cd backend
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Frontend setup
echo ""
echo "Setting up frontend..."
cd frontend
npm install
cd ..

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Place MP4 video files in ./videos/"
echo "  2. Run ./start.sh to launch both backend and frontend"
echo "  3. Open http://localhost:5173"
