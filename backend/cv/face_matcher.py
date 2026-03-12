import logging

import numpy as np

logger = logging.getLogger(__name__)


class FaceMatcher:
    """InsightFace-based face embedding extraction and comparison."""

    def __init__(self, model_name: str = "buffalo_sc", device: str = "cpu"):
        from insightface.app import FaceAnalysis

        providers = ["CPUExecutionProvider"]
        if device == "cuda":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        self._app = FaceAnalysis(name=model_name, providers=providers)
        self._app.prepare(ctx_id=0, det_size=(320, 320))
        logger.info("FaceMatcher loaded model=%s device=%s", model_name, device)

    def extract_embedding(self, image: np.ndarray) -> np.ndarray | None:
        """Extract face embedding from a BGR image.

        Returns 512-dim normalized embedding, or None if no face detected.
        If multiple faces, returns the largest (by bounding box area).
        """
        faces = self._app.get(image)
        if not faces:
            return None

        # Pick the largest face by bbox area
        best = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        emb = best.normed_embedding
        if emb is None:
            return None
        return emb.astype(np.float32)

    @staticmethod
    def compare(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two normalized embeddings."""
        return float(np.dot(emb1, emb2))
