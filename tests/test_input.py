from unittest.mock import patch, MagicMock

from kindle_screenshot.input import is_kindle_running, activate_kindle, send_right_arrow


def test_is_kindle_running_true():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="true\n", returncode=0)
        assert is_kindle_running() is True


def test_is_kindle_running_false():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="false\n", returncode=0)
        assert is_kindle_running() is False


def test_is_kindle_running_calls_osascript():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="true\n", returncode=0)
        is_kindle_running()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"


def test_activate_kindle_calls_osascript_with_activate():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        activate_kindle()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"
        joined = " ".join(cmd)
        assert "Kindle" in joined
        assert "activate" in joined


def test_send_right_arrow_uses_key_code_124():
    # macOS の右矢印キーは key code 124
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        send_right_arrow()
        cmd = mock_run.call_args[0][0]
        joined = " ".join(cmd)
        assert "124" in joined
        assert "key code" in joined
