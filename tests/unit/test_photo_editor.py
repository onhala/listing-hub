import io
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image, ImageDraw

from listing_hub.ai.photo_editor import (
    apply_box_blur,
    apply_background_bokeh,
    process_photo_pipeline
)

def create_synthetic_image_bytes(width=200, height=200, color="blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(img)
    # Nakreslíme žlutý kruh uprostřed a bílý obdélník pro SPZ
    draw.ellipse([(50, 50), (150, 150)], fill="yellow")
    draw.rectangle([(80, 140), (120, 160)], fill="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_apply_box_blur():
    img_bytes = create_synthetic_image_bytes(200, 200)
    # Box přes bílý obdélník: x od 80 do 120 (0.4 do 0.6), y od 140 do 160 (0.7 do 0.8)
    blurred_bytes = apply_box_blur(img_bytes, box_coords=(0.4, 0.7, 0.6, 0.8), blur_radius=10)
    
    assert len(blurred_bytes) > 0
    with Image.open(io.BytesIO(blurred_bytes)) as out_img:
        assert out_img.size == (200, 200)
        assert out_img.format == "JPEG"

def test_apply_background_bokeh_with_mocked_rembg():
    img_bytes = create_synthetic_image_bytes(100, 100)
    
    # Mock rembg.remove to return a binary mask
    mock_mask = Image.new("L", (100, 100), 0)
    draw = ImageDraw.Draw(mock_mask)
    draw.rectangle([(25, 25), (75, 75)], fill=255)

    # Mock rembg in sys.modules
    mock_rembg = MagicMock()
    mock_rembg.remove.return_value = mock_mask

    with patch.dict("sys.modules", {"rembg": mock_rembg}):
        with patch("listing_hub.ai.photo_editor.get_rembg_session", return_value=MagicMock()):
            bokeh_bytes = apply_background_bokeh(img_bytes, blur_radius=15, ground_gradient=True)
            assert len(bokeh_bytes) > 0
            with Image.open(io.BytesIO(bokeh_bytes)) as out_img:
                assert out_img.size == (100, 100)
                assert out_img.format == "JPEG"

def test_apply_background_bokeh_fallback_without_rembg():
    img_bytes = create_synthetic_image_bytes(100, 100)
    with patch("listing_hub.ai.photo_editor.get_rembg_session", return_value=None):
        bokeh_bytes = apply_background_bokeh(img_bytes, blur_radius=15)
        assert len(bokeh_bytes) > 0
        with Image.open(io.BytesIO(bokeh_bytes)) as out_img:
            assert out_img.size == (100, 100)

def test_process_photo_pipeline():
    img_bytes = create_synthetic_image_bytes(100, 100)
    operations = [
        {"type": "bokeh", "radius": 10},
        {"type": "blur_box", "box": [0.2, 0.2, 0.8, 0.4], "radius": 15}
    ]
    with patch("listing_hub.ai.photo_editor.get_rembg_session", return_value=None):
        result_bytes = process_photo_pipeline(img_bytes, operations)
        assert len(result_bytes) > 0
        with Image.open(io.BytesIO(result_bytes)) as out_img:
            assert out_img.size == (100, 100)
