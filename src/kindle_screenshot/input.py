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

# Kindle for Mac は `tell application "Kindle"` 構文をサポートしておらず、
# `tell application "Kindle" to activate` は -1728 エラーで失敗する（issue #9）。
# 代わりに System Events 経由で process の frontmost プロパティを true に設定する
# アクセシビリティ API を使う。is_kindle_running と同じ System Events 経路のため、
# 新たな権限要求は発生しない。
# `if exists process "Kindle"` ガードにより、Kindle が途中で終了した場合でも
# 例外を投げず、後続のキャプチャ失敗で中断扱いに合流できる。
_ACTIVATE_SCRIPT = '''
tell application "System Events"
    if exists process "Kindle" then
        set frontmost of process "Kindle" to true
    end if
end tell
'''

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
