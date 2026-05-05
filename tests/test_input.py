# 注: ユニットテストでは AppleScript の実体動作（System Events 経由の frontmost 指示が
# 実際にウィンドウを前面化するか）は検証できない。subprocess.run をモックして、osascript
# に渡される AppleScript の文字列内容と返り値の取り扱いだけを確認する。
# AppleScript の実挙動は PR レビュー後の手動統合テストで担保する（issue #7 / #9 の経緯）。

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


def test_activate_kindle_uses_system_events_frontmost():
    """activate_kindle は System Events 経由で `set frontmost ... to true` を送る。

    Kindle for Mac は `tell application "Kindle"` をサポートしないため (-1728)、
    is_kindle_running と同じ System Events 経由のアクセシビリティ API を使う
    （issue #9）。
    """
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        activate_kindle()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"
        joined = " ".join(cmd)
        assert "System Events" in joined
        assert "frontmost" in joined
        assert 'process "Kindle"' in joined


def test_activate_kindle_does_not_use_tell_application_kindle():
    """リグレッション防止: `tell application "Kindle"` は使ってはいけない（-1728 エラー）。"""
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        activate_kindle()
        cmd = mock_run.call_args[0][0]
        joined = " ".join(cmd)
        assert 'tell application "Kindle"' not in joined


def test_activate_kindle_does_not_raise_when_kindle_not_running():
    """`if exists process "Kindle"` ガードにより、Kindle 未起動でも例外を投げない。

    osascript 自体は exit 0 で正常終了するため、subprocess.run も returncode=0
    を返す。後続のキャプチャ失敗で正常な中断扱いに合流する設計。
    """
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # 例外を投げないことを確認（明示的な assert は不要、ここに到達できれば OK）
        activate_kindle()
        # スクリプトに exists ガードが含まれていることをチェック
        cmd = mock_run.call_args[0][0]
        joined = " ".join(cmd)
        assert "exists process" in joined


def test_send_right_arrow_uses_key_code_124():
    # macOS の右矢印キーは key code 124
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        send_right_arrow()
        cmd = mock_run.call_args[0][0]
        joined = " ".join(cmd)
        assert "124" in joined
        assert "key code" in joined
