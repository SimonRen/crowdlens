# CrowdLens — Docker Compose Deployment

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- At least one `.mp4` video in `./videos/`

## Quick Start

```bash
git clone https://github.com/simonren/crowdlens.git
cd crowdlens
mkdir -p videos data
cp /path/to/your/video.mp4 videos/
docker compose up --build -d
```

Open **http://localhost:3000**

## Architecture

```
Browser :3000 → nginx (frontend) → /api/* proxy → backend :8000
                                                     ├─ FastAPI (REST + SSE + MJPEG)
                                                     ├─ CV worker (YOLO26n + MiVOLO V2)
                                                     └─ SQLite (./data/monitor.db)
```

## Configuration

All settings are environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|---|---|---|
| `DETECTION_MODEL` | `yolo26n` | YOLO model name |
| `CHILD_AGE_THRESHOLD` | `13` | Age below this = "child" |
| `CLASSIFICATION_INTERVAL` | `3` | Classify every N frames |
| `JPEG_QUALITY` | `70` | MJPEG stream quality (1-100) |
| `SNAPSHOT_INTERVAL` | `5` | DB snapshot interval (seconds) |
| `INPUT_RESOLUTION` | `640` | YOLO input resolution |
| `MAX_FPS` | `30` | Max processing FPS cap |
| `DEVICE` | `cpu` | Inference device: `cpu`, `cuda`, `mps`, `auto` |
| `DATABASE_PATH` | `/app/data/monitor.db` | SQLite database path |
| `VIDEOS_DIR` | `/app/videos` | Video files directory |

## NVIDIA GPU Support

```yaml
# docker-compose.yml — add to backend service:
services:
  backend:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - DEVICE=cuda
```

Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

## Volumes

| Mount | Purpose |
|---|---|
| `./videos:/app/videos` | Input video files (read-only by worker) |
| `./data:/app/data` | SQLite database (persists across restarts) |

## Commands

```bash
# Start
docker compose up -d --build

# View logs
docker compose logs -f backend

# Stop
docker compose down

# Rebuild after code changes
docker compose up -d --build --force-recreate
```

## Smoke Test

```bash
pip install httpx
python tests/test_smoke.py
```

Requires at least one video in `./videos/` and a running session.
