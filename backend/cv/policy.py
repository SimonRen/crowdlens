def classify_person(
    age: int | None,
    gender: str | None,
    det_score: float | None,
    threshold: int = 13,
) -> dict:
    """Derive classification from raw InsightFace outputs.

    Returns dict with classification, age_estimate, gender_estimate, confidence.
    """
    if age is None or gender is None or det_score is None:
        return {
            "classification": "unknown",
            "age_estimate": None,
            "gender_estimate": None,
            "confidence": None,
        }

    gender_mapped = "male" if gender == "M" else "female"

    if age < threshold:
        classification = "child"
    elif gender == "M":
        classification = "man"
    else:
        classification = "woman"

    return {
        "classification": classification,
        "age_estimate": float(age),
        "gender_estimate": gender_mapped,
        "confidence": float(det_score),
    }
