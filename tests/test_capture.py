import subprocess
from unittest.mock import patch, MagicMock
import pytest

from kindle_screenshot.capture import get_kindle_window_id, KindleNotFoundError


def _mock_run(stdout: str, returncode: int = 0):
    return MagicMock(stdout=stdout, stderr="", returncode=returncode)


def test_get_kindle_window_id_returns_int():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("12345\n")
        assert get_kindle_window_id() == 12345


def test_get_kindle_window_id_raises_when_kindle_not_running():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("NOT_RUNNING\n")
        with pytest.raises(KindleNotFoundError, match="起動していません"):
            get_kindle_window_id()


def test_get_kindle_window_id_raises_when_no_window():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("NO_WINDOW\n")
        with pytest.raises(KindleNotFoundError, match="ウィンドウ"):
            get_kindle_window_id()


def test_get_kindle_window_id_calls_osascript():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("999\n")
        get_kindle_window_id()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert "-e" in args


from pathlib import Path

from kindle_screenshot.capture import capture_window_to_png


def test_capture_window_to_png_runs_screencapture(tmp_path):
    out = tmp_path / "page.png"
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        # subprocess.run の戻り値は使わないが、ファイル作成を擬似的に行う
        def fake_run(*args, **kwargs):
            out.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024)
            return MagicMock(returncode=0)
        mock_run.side_effect = fake_run
        capture_window_to_png(window_id=12345, out=out)

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "screencapture"
        assert "-l" in called_cmd
        assert "12345" in called_cmd
        assert "-t" in called_cmd
        png_index = called_cmd.index("-t") + 1
        assert called_cmd[png_index] == "png"
        assert str(out) in called_cmd


def test_capture_window_to_png_raises_on_empty_file(tmp_path):
    out = tmp_path / "empty.png"
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        def fake_run(*args, **kwargs):
            out.write_bytes(b"")
            return MagicMock(returncode=0)
        mock_run.side_effect = fake_run
        with pytest.raises(RuntimeError, match="キャプチャ"):
            capture_window_to_png(window_id=12345, out=out)


def test_capture_window_to_png_raises_when_file_missing(tmp_path):
    out = tmp_path / "missing.png"
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RuntimeError, match="キャプチャ"):
            capture_window_to_png(window_id=12345, out=out)


from PIL import Image

from kindle_screenshot.capture import process_image


def _make_png(path: Path, size: tuple[int, int] = (400, 600), color: tuple[int, int, int] = (200, 100, 50)) -> Path:
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def test_process_image_no_crop_jpeg(tmp_path):
    src = _make_png(tmp_path / "src.png")
    dst = tmp_path / "out.jpg"
    process_image(src, dst, fmt="jpeg", quality=85)
    assert dst.exists()
    assert not src.exists()  # 中間 PNG は削除される
    with Image.open(dst) as im:
        assert im.format == "JPEG"
        assert im.size == (400, 600)


def test_process_image_no_crop_png(tmp_path):
    src = _make_png(tmp_path / "src.png", size=(300, 400))
    dst = tmp_path / "out.png"
    process_image(src, dst, fmt="png", quality=85)
    assert dst.exists()
    with Image.open(dst) as im:
        assert im.format == "PNG"
        assert im.size == (300, 400)


def test_process_image_crops_correctly(tmp_path):
    src = _make_png(tmp_path / "src.png", size=(400, 600))
    dst = tmp_path / "out.jpg"
    process_image(src, dst, fmt="jpeg", quality=85,
                  crop_top=60, crop_bottom=40, crop_left=10, crop_right=20)
    with Image.open(dst) as im:
        # 元 400x600 から 上60+下40+左10+右20 を除去
        assert im.size == (400 - 10 - 20, 600 - 60 - 40)
        assert im.size == (370, 500)


def test_process_image_invalid_crop_raises(tmp_path):
    src = _make_png(tmp_path / "src.png", size=(100, 100))
    dst = tmp_path / "out.jpg"
    with pytest.raises(ValueError, match="クロップ"):
        process_image(src, dst, fmt="jpeg", quality=85,
                      crop_top=60, crop_bottom=60)


def test_process_image_jpg_alias_treated_as_jpeg(tmp_path):
    src = _make_png(tmp_path / "src.png")
    dst = tmp_path / "out.jpg"
    process_image(src, dst, fmt="jpg", quality=85)
    with Image.open(dst) as im:
        assert im.format == "JPEG"
