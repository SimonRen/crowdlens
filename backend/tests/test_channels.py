import os
import tempfile
import pytest
from cv.channels import scan_videos_dir


def test_scan_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        channels = scan_videos_dir(d)
        assert channels == []


def test_scan_with_mp4_files():
    with tempfile.TemporaryDirectory() as d:
        # Create fake mp4 files
        for name in ["street-scene.mp4", "mall-crowd.mp4", "readme.txt"]:
            open(os.path.join(d, name), "w").close()
        channels = scan_videos_dir(d)
        assert len(channels) == 2
        ids = [c["id"] for c in channels]
        assert "street-scene" in ids
        assert "mall-crowd" in ids


def test_scan_nonexistent_dir():
    channels = scan_videos_dir("/nonexistent/path")
    assert channels == []


def test_label_formatting():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "my-test_video.mp4"), "w").close()
        channels = scan_videos_dir(d)
        assert channels[0]["label"] == "My Test Video"
