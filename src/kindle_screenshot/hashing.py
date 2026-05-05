"""画像ハッシュと連続重複検出。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


def compute_hash(img_path: Path) -> str:
    """画像を 64x64 グレースケールに縮小し、ピクセルバイト列の SHA256 を返す。

    完全に同一フレームかどうかの判定用。perceptual hash ではなく
    生ピクセル比較なので、わずかなノイズでも別ハッシュになる。Kindle で
    同じページを撮り直したときは厳密にバイト一致するため、これで十分。
    """
    with Image.open(img_path) as img:
        small = img.convert("L").resize((64, 64))
        return hashlib.sha256(small.tobytes()).hexdigest()


class DuplicateDetector:
    """連続して同じハッシュが N 回現れたら停止判定する。

    Kindle で右矢印を押し続けて末尾を超えると、同じページのキャプチャが
    続く。N 連続で同一ハッシュを検出したら、それ以降は無効データとして
    PDF から末尾 N-1 枚を除外する。
    """

    def __init__(self, stop_after: int) -> None:
        if stop_after < 1:
            raise ValueError("stop_after は 1 以上である必要があります")
        self.stop_after = stop_after
        self._last_hash: str | None = None
        self._consecutive_count = 0

    def add(self, h: str) -> bool:
        """ハッシュを 1 件追加。連続して stop_after 回同じなら True を返す。"""
        if h == self._last_hash:
            self._consecutive_count += 1
        else:
            self._last_hash = h
            self._consecutive_count = 1
        return self._consecutive_count >= self.stop_after

    @property
    def trim_count(self) -> int:
        """末尾から削除すべき重複ページ数（実ページを 1 枚残す）。"""
        return max(0, self._consecutive_count - 1)
