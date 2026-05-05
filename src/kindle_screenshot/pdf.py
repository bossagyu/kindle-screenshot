"""画像群から PDF を生成する。"""

from __future__ import annotations

from pathlib import Path

import img2pdf


def images_to_pdf(images: list[Path], output: Path) -> None:
    """画像ファイルのリストを 1 つの PDF にまとめる。

    img2pdf は JPEG/PNG を再エンコードせずそのまま埋め込むため、
    画質劣化は発生しない（PNG はロスレス、JPEG はバイト単位で保持）。
    """
    if not images:
        raise ValueError("画像リストが空です。1 枚以上必要です。")
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = img2pdf.convert([str(p) for p in images])
    output.write_bytes(pdf_bytes)
