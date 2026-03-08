from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    detection_model: str = "yolo11n"
    child_age_threshold: int = 13
    classification_interval: int = 3
    jpeg_quality: int = 70
    snapshot_interval: int = 5
    input_resolution: int = 640
    database_path: str = "/app/data/monitor.db"
    videos_dir: str = "/app/videos"

    model_config = {"env_prefix": ""}


@lru_cache
def get_settings() -> Settings:
    return Settings()
