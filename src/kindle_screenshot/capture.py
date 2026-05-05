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


def process_image(
    src_png: Path,
    dst: Path,
    fmt: str,
    quality: int,
    crop_top: int = 0,
    crop_bottom: int = 0,
    crop_left: int = 0,
    crop_right: int = 0,
) -> None:
    """PNG 中間ファイルを読み、余白を除去して目的形式で保存。中間ファイルは削除。

    Args:
        src_png: 入力 PNG パス（処理後に削除される）
        dst: 出力先パス
        fmt: "jpeg" | "jpg" | "png"
        quality: JPEG 品質 (1-100)、PNG 時は無視
        crop_top, crop_bottom, crop_left, crop_right: 各辺から削るピクセル数
    """
    fmt_norm = "jpeg" if fmt.lower() in ("jpg", "jpeg") else "png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(src_png) as img:
            if any((crop_top, crop_bottom, crop_left, crop_right)):
                w, h = img.size
                left = crop_left
                top = crop_top
                right = w - crop_right
                bottom = h - crop_bottom
                if left >= right or top >= bottom:
                    raise ValueError(
                        f"クロップ値が画像サイズを超えています: image={w}x{h}, "
                        f"crops=top{crop_top}/bottom{crop_bottom}/left{crop_left}/right{crop_right}"
                    )
                img = img.crop((left, top, right, bottom))

            if fmt_norm == "jpeg":
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(dst, "JPEG", quality=quality, optimize=True)
            else:
                img.save(dst, "PNG", optimize=True)
    finally:
        src_png.unlink(missing_ok=True)
