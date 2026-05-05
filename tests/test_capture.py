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
