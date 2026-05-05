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
