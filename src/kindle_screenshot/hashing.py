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
