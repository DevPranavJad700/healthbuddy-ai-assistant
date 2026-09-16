"""Tests for Multimodal Medical Vision Service."""

import base64
import pytest
from app.services.vision_service import vision_service, MAX_IMAGE_SIZE_BYTES


@pytest.mark.asyncio
async def test_parse_valid_image_data_uri():
    # 1x1 transparent PNG base64
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    data_uri = f"data:image/png;base64,{tiny_png_b64}"

    mime_type, clean_b64, raw_bytes = vision_service.parse_image_data(data_uri)
    assert mime_type == "image/png"
    assert clean_b64 == tiny_png_b64
    assert len(raw_bytes) > 0


@pytest.mark.asyncio
async def test_parse_invalid_mime_type():
    with pytest.raises(ValueError, match="Unsupported image format"):
        vision_service.parse_image_data("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@pytest.mark.asyncio
async def test_parse_image_size_limit():
    fake_large_bytes = b"x" * (MAX_IMAGE_SIZE_BYTES + 1024)
    large_b64 = base64.b64encode(fake_large_bytes).decode("ascii")
    with pytest.raises(ValueError, match="exceeds maximum permitted size"):
        vision_service.parse_image_data(f"data:image/jpeg;base64,{large_b64}")


@pytest.mark.asyncio
async def test_vision_heuristic_fallback_medication():
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    data_uri = f"data:image/png;base64,{tiny_png_b64}"

    result = await vision_service.analyze_medical_image(
        image_data=data_uri,
        user_query="Can you read this prescription label?",
        image_type="medication_label",
    )

    assert "Medication Label" in result
    assert "Clinical Vision Advisory" in result
    assert "Pharmacist Discussion Guide" in result


@pytest.mark.asyncio
async def test_vision_heuristic_fallback_rash():
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    data_uri = f"data:image/png;base64,{tiny_png_b64}"

    result = await vision_service.analyze_medical_image(
        image_data=data_uri,
        user_query="I have an itchy red rash on my arm",
        image_type="rash",
    )

    assert "Clinical Visual Assessment" in result
    assert "Urgent Warning Signs" in result
    assert "Clinical Vision Advisory" in result
