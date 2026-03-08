import numpy as np


class FaceClassifier:
    def __init__(self, det_size: tuple[int, int] = (640, 640), det_thresh: float = 0.5):
        from insightface.app import FaceAnalysis
        self.app = FaceAnalysis(
            name="buffalo_l",
            allowed_modules=["detection", "genderage"],
            providers=["CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=0, det_thresh=det_thresh, det_size=det_size)

    def analyze_crop(self, crop: np.ndarray) -> dict | None:
        """Run face analysis on a person crop.

        Returns dict with age, gender, det_score or None if no face found.
        """
        if crop.shape[0] < 20 or crop.shape[1] < 20:
            return None

        faces = self.app.get(crop, max_num=1)
        if not faces:
            return None

        face = faces[0]
        return {
            "age": face.age,
            "gender": face.sex,  # 'M' or 'F'
            "det_score": float(face.det_score),
        }
