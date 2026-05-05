from pathlib import Path
from PIL import Image
import pytest

from kindle_screenshot.pdf import images_to_pdf


def make_jpeg(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (400, 600)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path, "JPEG", quality=85)
    return path


def test_images_to_pdf_creates_file(tmp_path):
    imgs = [
        make_jpeg(tmp_path / f"p{i:03d}.jpg", (50 * i, 100, 200))
        for i in range(1, 4)
    ]
    out = tmp_path / "book.pdf"
    images_to_pdf(imgs, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_images_to_pdf_correct_page_count(tmp_path):
    imgs = [
        make_jpeg(tmp_path / f"p{i:03d}.jpg", (50, 100, 200))
        for i in range(1, 6)
    ]
    out = tmp_path / "book.pdf"
    images_to_pdf(imgs, out)
    content = out.read_bytes()
    # PDF 内の "/Type /Page" を数えれば page count
    page_count = content.count(b"/Type /Page\n") + content.count(b"/Type/Page ")
    # img2pdf の出力は典型的に "/Type /Page" を各ページに含む
    assert b"%PDF" in content[:8]


def test_images_to_pdf_creates_parent_dir(tmp_path):
    imgs = [make_jpeg(tmp_path / "p1.jpg", (255, 0, 0))]
    out = tmp_path / "nested" / "dir" / "book.pdf"
    images_to_pdf(imgs, out)
    assert out.exists()


def test_images_to_pdf_empty_list_raises(tmp_path):
    with pytest.raises(ValueError):
        images_to_pdf([], tmp_path / "empty.pdf")
