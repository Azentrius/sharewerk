# SPDX-License-Identifier: Apache-2.0
"""The images of the Chrome Web Store listing (docs/chrome-web-store/) exist in the sizes the store
asks for, and docs/chrome-web-store.md names only images that exist."""

import re
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "chrome-web-store"

SIZES = {
    "store-icon-128.png": (128, 128),
    "promo-small.png": (440, 280),
    **{f"screenshot-{n}-{lang}.png": (1280, 800) for n in (1, 2, 3) for lang in ("en", "de")},
}


@pytest.mark.parametrize("name,size", sorted(SIZES.items()))
def test_each_image_has_the_size_the_store_asks_for(name, size):
    with Image.open(FOLDER / name) as image:
        assert image.size == size


def test_the_store_icon_keeps_a_transparent_margin_of_16_pixels():
    with Image.open(FOLDER / "store-icon-128.png") as image:
        alpha = image.convert("RGBA").getchannel("A")
        assert alpha.getbbox() == (16, 16, 112, 112)


def test_the_listing_names_only_images_that_exist():
    text = (ROOT / "docs" / "chrome-web-store.md").read_text(encoding="utf-8")
    named = set(re.findall(r"[a-z0-9-]+\.png", text))
    named |= {f"screenshot-{n}-{lang}.png" for n in (1, 2, 3) for lang in ("en", "de")}  # named as a range
    assert {n for n in named if not (FOLDER / n).is_file()} == set()
