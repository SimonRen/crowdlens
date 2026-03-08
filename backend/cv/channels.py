import os
from pathlib import Path


def scan_videos_dir(videos_dir: str) -> list[dict]:
    """Scan directory for MP4 files and return channel list."""
    channels = []
    path = Path(videos_dir)
    if not path.exists():
        return channels

    for f in sorted(path.glob("*.mp4")):
        channel_id = f.stem  # filename without extension
        channels.append({
            "id": channel_id,
            "filename": f.name,
            "label": channel_id.replace("-", " ").replace("_", " ").title(),
        })
    return channels
