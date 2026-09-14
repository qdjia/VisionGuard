from visionguard.ocr.evaluator import character_error_rate, levenshtein_distance


def test_levenshtein_and_cer_for_chinese_text() -> None:
    assert levenshtein_distance("出版审核", "出版审校") == 1
    assert character_error_rate("出版审核", "出版审校") == 0.25


def test_cer_empty_ground_truth_has_defined_behavior() -> None:
    assert character_error_rate("", "") == 0.0
    assert character_error_rate("unexpected", "") == 1.0
