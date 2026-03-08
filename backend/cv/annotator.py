import numpy as np
import supervision as sv

# Classification -> color mapping
CLASS_COLORS = {
    "man": sv.Color.from_hex("#3B82F6"),
    "woman": sv.Color.from_hex("#EC4899"),
    "child": sv.Color.from_hex("#22C55E"),
    "unknown": sv.Color.from_hex("#6B7280"),
}

CLASS_TO_ID = {"man": 0, "woman": 1, "child": 2, "unknown": 3}
PALETTE = sv.ColorPalette([
    sv.Color.from_hex("#3B82F6"),  # man = blue
    sv.Color.from_hex("#EC4899"),  # woman = pink
    sv.Color.from_hex("#22C55E"),  # child = green
    sv.Color.from_hex("#6B7280"),  # unknown = gray
])


class FrameAnnotator:
    def __init__(self):
        self.box_annotator = sv.BoxAnnotator(
            thickness=2, color=PALETTE, color_lookup=sv.ColorLookup.CLASS,
        )
        self.label_annotator = sv.LabelAnnotator(
            text_scale=0.5, text_padding=5, text_color=sv.Color.WHITE,
            color=PALETTE, color_lookup=sv.ColorLookup.CLASS,
        )

    def annotate(
        self,
        frame: np.ndarray,
        detections: sv.Detections,
        classifications: dict[int, dict],
    ) -> np.ndarray:
        """Draw bounding boxes and labels on frame.

        Args:
            frame: BGR frame
            detections: supervision Detections from ultralytics result
            classifications: mapping of track_id -> {classification, confidence}
        """
        if len(detections) == 0:
            return frame

        # Override class_id to map classification -> palette index
        labels = []
        new_class_ids = []
        for i in range(len(detections)):
            tid = detections.tracker_id[i] if detections.tracker_id is not None else i
            info = classifications.get(tid, {})
            cls = info.get("classification", "unknown")
            conf = info.get("confidence")

            new_class_ids.append(CLASS_TO_ID.get(cls, 3))

            if cls == "unknown":
                labels.append(f"Person #{tid}")
            else:
                age = info.get("age")
                age_str = f" ~{int(age)}y" if age is not None else ""
                labels.append(f"{cls.capitalize()} #{tid}{age_str}")

        detections.class_id = np.array(new_class_ids)

        annotated = self.box_annotator.annotate(scene=frame.copy(), detections=detections)
        annotated = self.label_annotator.annotate(scene=annotated, detections=detections, labels=labels)
        return annotated
