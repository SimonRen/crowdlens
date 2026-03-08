import numpy as np
import torch
from PIL import Image


# Text prompts for zero-shot classification
LABELS = ["an adult man", "an adult woman", "a young child"]
LABEL_MAP = {0: "man", 1: "woman", 2: "child"}


class PersonClassifier:
    """Full-body CLIP classifier. Works from any angle — no face needed."""

    def __init__(self):
        from transformers import CLIPProcessor, CLIPModel
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.model.eval()

        # Pre-tokenize text labels once
        self._text_inputs = self.processor(
            text=[f"a photo of {l}" for l in LABELS],
            return_tensors="pt",
            padding=True,
        )

    def classify_crop(self, crop: np.ndarray) -> dict | None:
        """Classify a person crop as man/woman/child using CLIP.

        Args:
            crop: BGR numpy array (person bounding box crop)

        Returns:
            dict with classification and confidence, or None if crop too small.
        """
        if crop.shape[0] < 40 or crop.shape[1] < 20:
            return None

        # Convert BGR → RGB → PIL
        rgb = crop[:, :, ::-1]
        pil_img = Image.fromarray(rgb)

        # Process image
        image_inputs = self.processor(images=pil_img, return_tensors="pt")

        with torch.no_grad():
            outputs = self.model(
                pixel_values=image_inputs["pixel_values"],
                input_ids=self._text_inputs["input_ids"],
                attention_mask=self._text_inputs["attention_mask"],
            )
            # Softmax over logits_per_image to get probabilities
            probs = outputs.logits_per_image.softmax(dim=-1)[0]

        best_idx = probs.argmax().item()
        confidence = probs[best_idx].item()

        return {
            "classification": LABEL_MAP[best_idx],
            "confidence": round(confidence, 3),
        }
