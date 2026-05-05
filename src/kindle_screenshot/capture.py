"""Kindle ウィンドウのキャプチャと画像処理。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image


class KindleNotFoundError(RuntimeError):
    """Kindle.app が起動していない、またはウィンドウが見つからない。"""


# Kindle for Mac は AppleScript の `id` プロパティに対応していない（-1728 エラー）。
# 代わりに `position` と `size` を取得して `screencapture -R x,y,w,h` でキャプチャする。
# `as string` で連結することでロケール依存の小数点表記（カンマ vs ピリオド）を回避。
_WINDOW_BOUNDS_SCRIPT = """
tell application "System Events"
    if not (exists process "Kindle") then
        return "NOT_RUNNING"
    end if
    tell process "Kindle"
        if (count of windows) = 0 then
            return "NO_WINDOW"
        end if
        try
            set p to position of front window
            set s to size of front window
            return (item 1 of p as string) & "," & (item 2 of p as string) & "," & (item 1 of s as string) & "," & (item 2 of s as string)
        on error
            return "NO_WINDOW"
        end try
    end tell
end tell
"""


def get_kindle_window_bounds() -> tuple[int, int, int, int]:
    """Kindle.app のフロントウィンドウの位置とサイズを取得する。

    Returns:
        (x, y, width, height) のタプル。x, y は論理ピクセル座標で、
        マルチディスプレイ環境では負の値になり得る。

    Raises:
        KindleNotFoundError: Kindle 未起動 / ウィンドウなし / 想定外の osascript 出力
    """
    result = subprocess.run(
        ["osascript", "-e", _WINDOW_BOUNDS_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip()
    if out == "NOT_RUNNING":
        raise KindleNotFoundError("Kindle.app が起動していません。アプリを起動して書籍を開いてください。")
    if out == "NO_WINDOW":
        raise KindleNotFoundError("Kindle のウィンドウが見つかりません。書籍を開いてください。")
    return _parse_bounds(out)


def _parse_bounds(raw: str) -> tuple[int, int, int, int]:
    """osascript 出力 "x,y,w,h" を 4 要素タプルにパースする。

    想定外の形式（カンマ区切りでない、要素数 != 4、非数値）の場合は
    KindleNotFoundError に翻訳する（M3 と同じ精神でユーザーに分かる
    エラーメッセージにする）。
    """
    parts = raw.split(",")
    if len(parts) != 4:
        raise KindleNotFoundError(
            f"Kindle ウィンドウの位置/サイズの取得に失敗しました（osascript 出力: {raw!r}）"
        )
    try:
        x, y, w, h = (int(p.strip()) for p in parts)
    except ValueError as e:
        raise KindleNotFoundError(
            f"Kindle ウィンドウの位置/サイズが数値として解釈できません（osascript 出力: {raw!r}）"
        ) from e
    return x, y, w, h


def capture_region_to_png(bounds: tuple[int, int, int, int], out: Path) -> None:
    """指定矩形領域 (x, y, w, h) を PNG でキャプチャする。

    `-R x,y,w,h` で領域指定、`-x` で無音化、`-t png` で常に可逆形式。
    後段で必要なら PIL で JPEG に変換する（screencapture の JPEG は品質
    指定不可なので、PNG を経由して品質を厳密に制御する設計にしている）。

    座標系は論理ピクセル（ポイント）。Retina ディスプレイでも AppleScript の
    position/size がポイント値で返るので整合する。マルチディスプレイ環境で
    上方向のサブディスプレイにある場合 y は負の値になるが、screencapture -R
    は負の座標も受け付ける。
    """
    x, y, w, h = bounds
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["screencapture", "-R", f"{x},{y},{w},{h}", "-t", "png", "-x", str(out)],
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
