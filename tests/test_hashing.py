from pathlib import Path
from PIL import Image
import pytest

from kindle_screenshot.hashing import compute_hash


def make_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path)
    return path


def test_compute_hash_same_image_same_hash(tmp_path):
    a = make_image(tmp_path / "a.png", (255, 0, 0))
    b = make_image(tmp_path / "b.png", (255, 0, 0))
    assert compute_hash(a) == compute_hash(b)


def test_compute_hash_different_images_different_hash(tmp_path):
    a = make_image(tmp_path / "a.png", (255, 0, 0))
    b = make_image(tmp_path / "b.png", (0, 0, 255))
    assert compute_hash(a) != compute_hash(b)


def test_compute_hash_returns_hex_string(tmp_path):
    a = make_image(tmp_path / "a.png", (128, 128, 128))
    h = compute_hash(a)
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)  # 16進文字列として有効
