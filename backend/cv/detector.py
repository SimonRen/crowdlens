import numpy as np


class PersonDetector:
    def __init__(self, model_name: str = "yolo11n.pt", input_size: int = 640):
        from ultralytics import YOLO
        self.model = YOLO(model_name)
        self.input_size = input_size

    def detect_and_track(self, frame: np.ndarray) -> dict:
        """Run detection + tracking on a frame.

        Returns dict with keys: boxes_xyxy, track_ids, confidences, result (raw).
        """
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],  # person only
            conf=0.5,
            iou=0.7,
            imgsz=self.input_size,
            verbose=False,
        )
        result = results[0]

        if result.boxes.id is None:
            return {
                "boxes_xyxy": np.empty((0, 4)),
                "track_ids": [],
                "confidences": np.empty(0),
                "result": result,
            }

        return {
            "boxes_xyxy": result.boxes.xyxy.cpu().numpy(),
            "track_ids": result.boxes.id.int().cpu().tolist(),
            "confidences": result.boxes.conf.cpu().numpy(),
            "result": result,
        }

    def reset_tracker(self):
        """Reset ByteTrack state (call on video loop restart)."""
        if hasattr(self.model, "predictor") and self.model.predictor is not None:
            for tracker in self.model.predictor.trackers:
                tracker.reset()
