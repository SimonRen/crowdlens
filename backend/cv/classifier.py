import numpy as np
import torch
from transformers import AutoModelForImageClassification, AutoConfig, AutoImageProcessor


class PersonClassifier:
    """MiVOLO V2 age+gender classifier. Works from full body crops — no face needed."""

    def __init__(self, child_age_threshold: int = 13, gender_confidence_threshold: float = 0.6,
                 min_crop_height: int = 80, device: str = "cpu"):
        self.child_age_threshold = child_age_threshold
        self.gender_confidence_threshold = gender_confidence_threshold
        self.min_crop_height = min_crop_height
        self._device = torch.device(device)

        self.config = AutoConfig.from_pretrained(
            "iitolstykh/mivolo_v2", trust_remote_code=True,
        )
        self.model = AutoModelForImageClassification.from_pretrained(
            "iitolstykh/mivolo_v2", trust_remote_code=True, dtype=torch.float32,
        )
        self.model.eval()
        self.model.to(self._device)
        self.processor = AutoImageProcessor.from_pretrained(
            "iitolstykh/mivolo_v2", trust_remote_code=True,
        )
        self._gender_labels = self.config.gender_id2label

    def classify_batch(self, crops: list[np.ndarray]) -> list[dict | None]:
        """Classify a batch of person body crops.

        Args:
            crops: list of BGR numpy arrays (person bounding box crops)

        Returns:
            list of dicts with classification/confidence/age, or None for too-small crops.
        """
        results: list[dict | None] = [None] * len(crops)
        valid_indices: list[int] = []
        valid_crops: list[np.ndarray] = []

        for i, crop in enumerate(crops):
            if crop.shape[0] < self.min_crop_height or crop.shape[1] < 20:
                continue
            # BGR → RGB for processor
            valid_crops.append(crop[:, :, ::-1].copy())
            valid_indices.append(i)

        if not valid_crops:
            return results

        # Process all crops in one batch
        body_input = self.processor(images=valid_crops)["pixel_values"]
        body_input = body_input.to(dtype=self.model.dtype, device=self.model.device)

        # MiVOLO V2 with_persons_model expects 6-channel input (face + body concat).
        # When no face crop is available, pass zeros for the face channels.
        faces_input = torch.zeros_like(body_input)
        concat_input = torch.cat((faces_input, body_input), dim=1)

        with torch.no_grad():
            output = self.model(concat_input=concat_input)

        for j, idx in enumerate(valid_indices):
            age = output.age_output[j].item()
            gender_idx = output.gender_class_idx[j].item()
            gender_prob = output.gender_probs[j].item()
            gender = self._gender_labels[gender_idx]

            # Derive classification from age + gender
            if age < self.child_age_threshold:
                classification = "child"
            elif gender_prob < self.gender_confidence_threshold:
                classification = "unknown"
            elif gender.lower() in ("male", "man"):
                classification = "man"
            else:
                classification = "woman"

            results[idx] = {
                "classification": classification,
                "confidence": round(gender_prob, 3),
                "age": round(age, 1),
            }

        return results
