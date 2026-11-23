"""Images and 1.x recordings shared by the display tests."""

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

ASSETS = Path(__file__).with_name("assets")
REPOSITORY_ASSETS = Path(__file__).parents[2] / "assets"
# color conversions of the 1.x WaveshareDisplay / PimoroniDisplay
RECORDED_1X: dict[str, Any] = json.loads((ASSETS / "display_1x.json").read_text())


def sample_image() -> Image.Image:
    """A 64x48 image with many colors (same as when recording 1.x)."""
    image = Image.new("RGB", (64, 48))
    image.putdata(
        [
            ((x * 4) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
            for y in range(48)
            for x in range(64)
        ]
    )
    return image


def recorded_images() -> dict[str, Image.Image]:
    with Image.open(REPOSITORY_ASSETS / "waveshare.bmp") as photo:
        photo.load()
    return {"waveshare.bmp": photo, "sample": sample_image()}


def digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()
