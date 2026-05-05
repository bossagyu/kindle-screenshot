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


def capture_window_to_png(window_id: int, out: Path) -> None:
    """指定ウィンドウ ID の内容を PNG でキャプチャする。

    `-x` で無音化、`-t png` で常に可逆形式。後段で必要なら PIL で
    JPEG に変換する（screencapture の JPEG は品質指定不可なので、
    PNG を経由して品質を厳密に制御する設計にしている）。
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["screencapture", "-l", str(window_id), "-t", "png", "-x", str(out)],
        check=True,
    )
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"キャプチャ失敗: {out}（権限不足の可能性）")
