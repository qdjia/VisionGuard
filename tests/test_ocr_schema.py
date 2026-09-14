from visionguard.schemas import BoundingBox, OCRResult, OCRScope, OCRTextBlock, OCRTiming


def test_ocr_schema_preserves_polygon_bbox_and_counts() -> None:
    block = OCRTextBlock(
        text="出版安全",
        confidence=0.96,
        polygon=[(10, 10), (90, 8), (92, 30), (12, 32)],
        bbox=BoundingBox(x1=10, y1=8, x2=92, y2=32),
        scope=OCRScope.FULL_IMAGE,
    )
    result = OCRResult(
        image_width=100,
        image_height=50,
        blocks=[block],
        full_text=block.text,
        timing=OCRTiming(total_ms=12.5),
        device="cpu",
        engine_name="PaddleOCR",
        raw_block_count=2,
        filtered_block_count=1,
    )

    payload = result.model_dump(mode="json")
    assert payload["blocks"][0]["polygon"][1] == [90.0, 8.0]
    assert payload["blocks"][0]["bbox"]["x2"] == 92.0
    assert payload["raw_block_count"] == 2


def test_empty_ocr_result_uses_empty_collections_not_none() -> None:
    result = OCRResult(
        image_width=20,
        image_height=10,
        timing=OCRTiming(),
        device="cpu",
        engine_name="fake",
    )

    assert result.blocks == []
    assert result.full_text == ""
