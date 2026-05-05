"""Kindle ウィンドウのキャプチャと画像処理。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image


class KindleNotFoundError(RuntimeError):
    """Kindle.app が起動していない、またはウィンドウが見つからない。"""


_WINDOW_ID_SCRIPT = """
tell application "System Events"
    if not (exists process "Kindle") then
        return "NOT_RUNNING"
    end if
    tell process "Kindle"
        if (count of windows) = 0 then
            return "NO_WINDOW"
        end if
        try
            return id of front window as string
        on error
            return "NO_WINDOW"
        end try
    end tell
end tell
"""


def get_kindle_window_id() -> int:
    """Kindle.app のフロントウィンドウ ID を取得する。

    Raises:
        KindleNotFoundError: Kindle 未起動 or ウィンドウなし
    """
    result = subprocess.run(
        ["osascript", "-e", _WINDOW_ID_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip()
    if out == "NOT_RUNNING":
        raise KindleNotFoundError("Kindle.app が起動していません。アプリを起動して書籍を開いてください。")
    if out == "NO_WINDOW":
        raise KindleNotFoundError("Kindle のウィンドウが見つかりません。書籍を開いてください。")
    return int(out)
