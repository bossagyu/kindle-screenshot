"""Kindle.app の制御とキー送信（osascript ラッパー）。"""

from __future__ import annotations

import subprocess


_IS_RUNNING_SCRIPT = '''
tell application "System Events"
    if exists process "Kindle" then
        return "true"
    else
        return "false"
    end if
end tell
'''

_ACTIVATE_SCRIPT = 'tell application "Kindle" to activate'

_RIGHT_ARROW_SCRIPT = 'tell application "System Events" to key code 124'


def is_kindle_running() -> bool:
    """Kindle.app プロセスが起動しているか判定する。"""
    result = subprocess.run(
        ["osascript", "-e", _IS_RUNNING_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == "true"


def activate_kindle() -> None:
    """Kindle.app を前面に出す。フォーカス奪取への対策として毎ループ前に呼ぶ。"""
    subprocess.run(
        ["osascript", "-e", _ACTIVATE_SCRIPT],
        check=True,
    )


def send_right_arrow() -> None:
    """右矢印キーを System Events 経由で送る（key code 124 = →）。"""
    subprocess.run(
        ["osascript", "-e", _RIGHT_ARROW_SCRIPT],
        check=True,
    )
