"""kindle-screenshot CLI のエントリポイントと引数パース。"""

from __future__ import annotations

import argparse
from datetime import datetime


def _quality_type(value: str) -> int:
    n = int(value)
    if not 1 <= n <= 100:
        raise argparse.ArgumentTypeError("--quality は 1〜100")
    return n


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("1 以上の整数を指定してください")
    return n


def _non_negative_int(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("0 以上の整数を指定してください")
    return n


def default_output_name() -> str:
    """`kindle-YYYYMMDD-HHMMSS.pdf` 形式のデフォルトファイル名を生成。"""
    return f"kindle-{datetime.now():%Y%m%d-%H%M%S}.pdf"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kindle-screenshot",
        description="Kindle for Mac で開いた書籍をスクリーンショットして PDF 化する。",
    )
    p.add_argument("-o", "--output", default=None,
                   help="出力 PDF ファイル名（デフォルト: kindle-YYYYMMDD-HHMMSS.pdf）")
    p.add_argument("-d", "--output-dir", default=".",
                   help="出力ディレクトリ（デフォルト: カレント）")
    p.add_argument("--delay", type=float, default=0.5,
                   help="ページ送り後のキャプチャ前待機秒数（デフォルト: 0.5）")
    p.add_argument("--format", choices=["jpeg", "png"], default="jpeg",
                   help="PDF 内画像形式（デフォルト: jpeg）")
    p.add_argument("--quality", type=_quality_type, default=85,
                   help="JPEG 品質 1-100（デフォルト: 85）")
    p.add_argument("--max-pages", type=_positive_int, default=2000,
                   help="安全弁: この枚数で強制停止（デフォルト: 2000）")
    p.add_argument("--stop-after", type=_positive_int, default=3,
                   help="同一ハッシュ N 連続で停止（デフォルト: 3）")
    p.add_argument("--countdown", type=_non_negative_int, default=3,
                   help="ループ開始前のカウントダウン秒数（デフォルト: 3）")
    p.add_argument("--crop-top", type=_non_negative_int, default=60,
                   help="ウィンドウ上部の除去 px（デフォルト: 60）")
    p.add_argument("--crop-bottom", type=_non_negative_int, default=40,
                   help="ウィンドウ下部の除去 px（デフォルト: 40）")
    p.add_argument("--crop-left", type=_non_negative_int, default=0,
                   help="左余白 px（デフォルト: 0）")
    p.add_argument("--crop-right", type=_non_negative_int, default=0,
                   help="右余白 px（デフォルト: 0）")
    return p


def main() -> int:
    """エントリポイント。次タスクで本実装。"""
    raise NotImplementedError("Task 10 で実装")
