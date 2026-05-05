"""kindle-screenshot CLI のエントリポイントと引数パース。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from kindle_screenshot.capture import (
    KindleNotFoundError,
    capture_region_to_png,
    get_kindle_window_bounds,
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


def _print_subprocess_error_guidance(e: subprocess.CalledProcessError) -> int:
    """subprocess の失敗内容を分析し、ユーザー向けガイダンスを stderr に表示する。

    設計 §6 に基づき、osascript / screencapture の失敗を権限不足の可能性として案内し、
    System Settings の該当ページへの導線を表示する。終了コード 3（権限不足）または 4
    （その他のキャプチャ失敗）を返す。
    """
    cmd0 = e.cmd[0] if e.cmd else ""
    stderr_text = (e.stderr or "").strip() if isinstance(e.stderr, str) else ""

    if cmd0 == "osascript":
        # osascript の失敗は (1) 権限不足 / (2) AppleScript 非対応の二大要因がある。
        # `(-1728)` は「指定要素を取り出せない」エラーで、Kindle アプリ側の AppleScript
        # 非対応（issue #7 / #9 の経緯）を示す可能性が高い。ロケール非依存の数値文字列で
        # 判定する（日本語/英語のエラーメッセージ本文に依存しない）。
        is_minus_1728 = "(-1728)" in stderr_text
        message_lines = [
            "ERROR: osascript の実行に失敗しました。考えられる原因:",
            "  1. Accessibility / Apple Events 権限不足",
            "     → System Settings > Privacy & Security > Accessibility に",
            "       Terminal（Terminal.app / iTerm2 等）を追加してください。",
            "       さらに System Settings > Privacy & Security > Automation でも",
            "       Terminal から System Events への許可が必要な場合があります。",
            "  2. Kindle アプリの AppleScript 非対応（バージョン互換性問題）",
            "     → 当ツールが対応していない Kindle のバージョンの可能性があります。",
            "       README の動作確認済みバージョンを確認してください。",
        ]
        if is_minus_1728:
            message_lines.append(
                "  ※ stderr に (-1728) が含まれています。これは AppleScript の互換性問題"
            )
            message_lines.append(
                "     を示す可能性が高いため、原因 2 を優先してご確認ください。"
            )
        message_lines.append(f"  詳細: {stderr_text}")
        print("\n".join(message_lines), file=sys.stderr)
        return 3
    if cmd0 == "screencapture":
        print(
            "ERROR: screencapture の実行に失敗しました（Screen Recording 権限不足、または\n"
            "  Kindle ウィンドウが消失した可能性）。\n"
            "  System Settings > Privacy & Security > Screen Recording に Terminal を追加してください。\n"
            f"  詳細: {stderr_text}",
            file=sys.stderr,
        )
        return 3
    print(f"ERROR: 外部コマンド失敗: {e}", file=sys.stderr)
    return 4


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
    p.add_argument("--keep-images", default=None, metavar="DIR",
                   help="指定ディレクトリに最終画像（page_NNNNN.<jpg|png>）を保存。"
                        "省略時は破棄。Claude Code への画像入力ワークフローで利用。")
    p.add_argument("--no-pdf", action="store_true",
                   help="PDF 生成をスキップ。--keep-images <DIR> の指定が必須。")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # issue #14: --no-pdf 単独指定はエラー（--keep-images が必須）。
    # parser.error() は内部で exit 2 を呼ぶ（argparse 標準のエラー終了コード）。
    if args.no_pdf and not args.keep_images:
        parser.error(
            "--no-pdf を指定する場合は --keep-images <dir> の指定が必要です"
        )

    output_name = args.output or default_output_name()
    output_path = Path(args.output_dir) / output_name

    print("Kindle for Mac で対象書籍の 1 ページ目を表示してください。")
    print("準備ができたら Enter を押してください...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("\nキャンセルしました。", file=sys.stderr)
        return 1

    try:
        running = is_kindle_running()
    except subprocess.CalledProcessError as e:
        return _print_subprocess_error_guidance(e)

    if not running:
        print("ERROR: Kindle.app が起動していません。アプリを起動してから再実行してください。",
              file=sys.stderr)
        return 2

    try:
        bounds = get_kindle_window_bounds()
    except KindleNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        return _print_subprocess_error_guidance(e)

    bx, by, bw, bh = bounds
    print(f"Kindle ウィンドウを検出しました（位置={bx},{by} サイズ={bw}x{bh}）")

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
                    capture_region_to_png(bounds, tmp_png)
                except (RuntimeError, subprocess.CalledProcessError) as e:
                    # 1 回だけリトライ。screencapture は対象ウィンドウが消滅すると
                    # CalledProcessError（returncode=1, "could not create image from window"）
                    # で失敗するため、RuntimeError と同等にリトライ対象とする（設計 §6:
                    # 「Kindle ウィンドウが途中で消えた → 中断扱い、PDF 化を提案」）。
                    print(f"  [{page_num}] キャプチャ失敗: {e} → リトライ", file=sys.stderr)
                    time.sleep(args.delay)
                    try:
                        capture_region_to_png(bounds, tmp_png)
                    except (RuntimeError, subprocess.CalledProcessError) as e2:
                        # 1 ページも取得できていない場合は権限不足の可能性が高い。
                        # CalledProcessError は外側の except 句に伝播させて HIGH #1
                        # の権限案内パスに合流させる。それ以外は終了コード 4 相当の
                        # 内部 RuntimeError として扱う。
                        if not captured_files:
                            if isinstance(e2, subprocess.CalledProcessError):
                                raise
                            print(
                                f"  [{page_num}] 再失敗: {e2} → 中断", file=sys.stderr
                            )
                            break
                        # 取得済みページがある場合は Ctrl+C と同等の中断扱いに合流させ、
                        # 取得済みページの PDF 化をユーザーに提案する（設計 §6）。
                        print(
                            f"  [{page_num}] 再失敗: {e2} → 中断扱い"
                            "（取得済みページで PDF 化を提案）",
                            file=sys.stderr,
                        )
                        interrupted = True
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
                # max-pages 到達時も末尾の連続重複は除外する。stop-after に届かず
                # 検出 break には入らなかったが、末尾数枚が同一ハッシュの場合は
                # 重複として PDF から除外するのが合理的（MEDIUM #1）。
                trim = detector.trim_count
                if trim > 0:
                    captured_files = captured_files[: len(captured_files) - trim]
                    print(f"末尾の連続重複 {trim} ページを除外しました。", file=sys.stderr)
        except KeyboardInterrupt:
            interrupted = True
            print("\n中断シグナルを受信しました。", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            # ループ内の osascript / screencapture が失敗した場合は権限不足の可能性が
            # 高い。設計 §6 に従い、終了コード 3 と System Settings の案内を表示する。
            return _print_subprocess_error_guidance(e)

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

        # issue #14: --keep-images 指定時は PDF 化前に画像をコピーする。
        # PDF 化失敗時にも画像が救出されるよう、コピーを先に実行する。
        # tempfile.TemporaryDirectory の with ブロック終了で元ファイルが消えるため、
        # コピーは必ずこの with ブロック内で完了させる。
        if args.keep_images:
            keep_dir = Path(args.keep_images)
            keep_dir.mkdir(parents=True, exist_ok=True)
            for src in captured_files:
                shutil.copy2(src, keep_dir / src.name)
            print(f"画像 {len(captured_files)} 件を保存: {keep_dir}")

        # issue #14: --no-pdf 指定時は PDF 化をスキップ。
        if args.no_pdf:
            print("PDF 化はスキップしました（--no-pdf）")
            print("完了。")
            return 0

        print(f"{len(captured_files)} ページを PDF 化中...")
        images_to_pdf(captured_files, output_path)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"出力: {output_path} ({size_mb:.1f} MB)")
        print("完了。")
        return 0
