import os
import pytest


def test_default_config():
    # Unset any env vars that might interfere
    for key in ["DETECTION_MODEL", "CHILD_AGE_THRESHOLD", "CLASSIFICATION_INTERVAL",
                "JPEG_QUALITY", "SNAPSHOT_INTERVAL", "INPUT_RESOLUTION", "DATABASE_PATH"]:
        os.environ.pop(key, None)

    # Re-import to get fresh defaults
    import importlib
    import config
    importlib.reload(config)
    settings = config.get_settings()

    assert settings.detection_model == "yolo11n"
    assert settings.child_age_threshold == 13
    assert settings.classification_interval == 3
    assert settings.jpeg_quality == 70
    assert settings.snapshot_interval == 5
    assert settings.input_resolution == 640
    assert settings.database_path == "/app/data/monitor.db"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("DETECTION_MODEL", "yolo26n")
    monkeypatch.setenv("CHILD_AGE_THRESHOLD", "10")
    monkeypatch.setenv("JPEG_QUALITY", "85")

    import importlib
    import config
    importlib.reload(config)
    settings = config.get_settings()

    assert settings.detection_model == "yolo26n"
    assert settings.child_age_threshold == 10
    assert settings.jpeg_quality == 85
