#!/bin/bash
set -e

echo "=== CrowdLens Setup ==="
echo ""

# Create required directories
mkdir -p videos data

# Backend setup
echo "[1/4] Setting up Python environment..."
cd backend
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
cd ..

# Download models
echo "[2/4] Downloading models..."
cd backend
source .venv/bin/activate
python -c "
from transformers import AutoModelForImageClassification, AutoConfig, AutoImageProcessor
print('  Downloading MiVOLO V2 (age+gender classifier)...')
AutoConfig.from_pretrained('iitolstykh/mivolo_v2', trust_remote_code=True)
AutoModelForImageClassification.from_pretrained('iitolstykh/mivolo_v2', trust_remote_code=True)
AutoImageProcessor.from_pretrained('iitolstykh/mivolo_v2', trust_remote_code=True)
print('  MiVOLO V2 ready.')

from ultralytics import YOLO
print('  Downloading YOLO26n (person detector)...')
YOLO('yolo26n.pt')
print('  YOLO26n ready.')
print('All models downloaded.')
"
cd ..

# Frontend setup
echo "[3/4] Setting up frontend..."
cd frontend
npm install --silent
cd ..

# Videos check
echo "[4/4] Checking for video files..."
VIDEO_COUNT=$(ls videos/*.mp4 2>/dev/null | wc -l | tr -d ' ')
if [ "$VIDEO_COUNT" = "0" ]; then
    echo ""
    echo "  No MP4 files found in ./videos/"
    echo "  Add crowd/street videos for testing:"
    echo "    - Download from https://www.pexels.com/search/videos/crowd%20walking/"
    echo "    - Or copy any MP4: cp /path/to/video.mp4 videos/"
else
    echo "  Found $VIDEO_COUNT video(s) in ./videos/"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
if [ "$VIDEO_COUNT" = "0" ]; then
    echo "  1. Place MP4 video files in ./videos/"
    echo "  2. Run ./start.sh"
else
    echo "  1. Run ./start.sh"
fi
echo "  Open http://localhost:5173"
