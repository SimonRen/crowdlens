from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    detection_model: str = "yolo26n"
    child_age_threshold: int = 13
    classification_interval: int = 3
    jpeg_quality: int = 70
    snapshot_interval: int = 5
    input_resolution: int = 640
    max_fps: int = 30
    device: str = "auto"  # "auto", "mps", "cuda", "cpu"
    database_path: str = "/app/data/monitor.db"
    videos_dir: str = "/app/videos"

    def resolve_device(self) -> str:
        import torch
        if self.device != "auto":
            return self.device
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    model_config = {"env_prefix": ""}


@lru_cache
def get_settings() -> Settings:
    return Settings()
