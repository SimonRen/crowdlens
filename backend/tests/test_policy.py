from cv.policy import classify_person


def test_classify_man():
    result = classify_person(age=30, gender="M", det_score=0.9, threshold=13)
    assert result["classification"] == "man"


def test_classify_woman():
    result = classify_person(age=25, gender="F", det_score=0.85, threshold=13)
    assert result["classification"] == "woman"


def test_classify_child_male():
    result = classify_person(age=8, gender="M", det_score=0.8, threshold=13)
    assert result["classification"] == "child"


def test_classify_child_female():
    result = classify_person(age=10, gender="F", det_score=0.7, threshold=13)
    assert result["classification"] == "child"


def test_classify_unknown_no_face():
    result = classify_person(age=None, gender=None, det_score=None, threshold=13)
    assert result["classification"] == "unknown"


def test_classify_custom_threshold():
    result = classify_person(age=14, gender="M", det_score=0.9, threshold=16)
    assert result["classification"] == "child"
    result2 = classify_person(age=14, gender="M", det_score=0.9, threshold=13)
    assert result2["classification"] == "man"
