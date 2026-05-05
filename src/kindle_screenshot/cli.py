"""kindle-screenshot CLI のエントリポイントと引数パース。"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from kindle_screenshot.capture import (
    KindleNotFoundError,
    capture_window_to_png,
    get_kindle_window_id,
    process_image,
)
from kindle_screenshot.hashing import DuplicateDetector, compute_hash
from kindle_screenshot.input import (
    activate_kindle,
    is_kindle_running,
    send_right_arrow,
)
from kindle_screenshot.pdf import images_to_pdf


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_name = args.output or default_output_name()
    output_path = Path(args.output_dir) / output_name

    print("Kindle for Mac で対象書籍の 1 ページ目を表示してください。")
    print("準備ができたら Enter を押してください...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("\nキャンセルしました。", file=sys.stderr)
        return 1

    if not is_kindle_running():
        print("ERROR: Kindle.app が起動していません。アプリを起動してから再実行してください。",
              file=sys.stderr)
        return 2

    try:
        window_id = get_kindle_window_id()
    except KindleNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"Kindle ウィンドウを検出しました（window_id={window_id}）")

    if args.countdown > 0:
        print(f"{args.countdown} 秒後に開始します。Kindle ウィンドウが前面にあることを確認してください...")
        for i in range(args.countdown, 0, -1):
            print(f"  {i}...")
            time.sleep(1)

    detector = DuplicateDetector(stop_after=args.stop_after)
    captured_files: list[Path] = []
    interrupted = False

    with tempfile.TemporaryDirectory(prefix="kindle-ss-") as tmpdir:
        tmp = Path(tmpdir)
        try:
            for page_num in range(1, args.max_pages + 1):
                activate_kindle()
                if page_num > 1:
                    send_right_arrow()
                time.sleep(args.delay)

                tmp_png = tmp / f"raw_{page_num:05d}.png"
                ext = "jpg" if args.format == "jpeg" else "png"
                final_path = tmp / f"page_{page_num:05d}.{ext}"

                try:
                    capture_window_to_png(window_id, tmp_png)
                except RuntimeError as e:
                    # 1 回だけリトライ
                    print(f"  [{page_num}] キャプチャ失敗: {e} → リトライ", file=sys.stderr)
                    time.sleep(args.delay)
                    try:
                        capture_window_to_png(window_id, tmp_png)
                    except RuntimeError as e2:
                        print(f"  [{page_num}] 再失敗: {e2} → 中断", file=sys.stderr)
                        break

                process_image(
                    tmp_png, final_path,
                    fmt=args.format, quality=args.quality,
                    crop_top=args.crop_top, crop_bottom=args.crop_bottom,
                    crop_left=args.crop_left, crop_right=args.crop_right,
                )
                captured_files.append(final_path)
                h = compute_hash(final_path)
                print(f"  [{page_num:>4}] hash={h[:8]}... ✓")

                if detector.add(h):
                    trim = detector.trim_count
                    print(f"末尾の重複 {trim} ページを除外します。")
                    captured_files = captured_files[: len(captured_files) - trim]
                    break
            else:
                print(f"WARNING: --max-pages {args.max_pages} に到達しました。"
                      "末尾検出に失敗した可能性があります。", file=sys.stderr)
        except KeyboardInterrupt:
            interrupted = True
            print("\n中断シグナルを受信しました。", file=sys.stderr)

        if interrupted:
            try:
                ans = input(
                    f"取得済みの {len(captured_files)} ページで PDF 化しますか？ [Y/n]: "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans not in ("", "y", "yes"):
                print("PDF 化を中止しました。", file=sys.stderr)
                return 130

        if not captured_files:
            print("ERROR: キャプチャされたページがありません。", file=sys.stderr)
            return 4

        print(f"{len(captured_files)} ページを PDF 化中...")
        images_to_pdf(captured_files, output_path)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"出力: {output_path} ({size_mb:.1f} MB)")
        print("完了。")
        return 0
