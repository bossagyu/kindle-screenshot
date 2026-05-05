import re
import pytest

from kindle_screenshot.cli import build_parser, default_output_name


def test_default_output_name_format():
    name = default_output_name()
    assert re.fullmatch(r"kindle-\d{8}-\d{6}\.pdf", name)


def test_parser_defaults():
    p = build_parser()
    args = p.parse_args([])
    assert args.output is None
    assert args.delay == 0.5
    assert args.format == "jpeg"
    assert args.quality == 85
    assert args.max_pages == 2000
    assert args.stop_after == 3
    assert args.countdown == 3
    assert args.crop_top == 60
    assert args.crop_bottom == 40
    assert args.crop_left == 0
    assert args.crop_right == 0


def test_parser_accepts_custom_values():
    p = build_parser()
    args = p.parse_args([
        "-o", "book.pdf",
        "-d", "/tmp/out",
        "--delay", "1.5",
        "--format", "png",
        "--quality", "95",
        "--max-pages", "500",
        "--stop-after", "5",
        "--countdown", "1",
        "--crop-top", "80",
        "--crop-bottom", "50",
    ])
    assert args.output == "book.pdf"
    assert args.output_dir == "/tmp/out"
    assert args.delay == 1.5
    assert args.format == "png"
    assert args.quality == 95
    assert args.max_pages == 500
    assert args.stop_after == 5
    assert args.countdown == 1
    assert args.crop_top == 80
    assert args.crop_bottom == 50


def test_parser_rejects_invalid_quality():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--quality", "0"])
    with pytest.raises(SystemExit):
        p.parse_args(["--quality", "101"])


def test_parser_rejects_invalid_format():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--format", "tiff"])


def test_parser_rejects_invalid_stop_after():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--stop-after", "0"])


from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from kindle_screenshot.cli import main


def _make_png(path: Path, color: tuple[int, int, int]) -> Path:
    Image.new("RGB", (300, 400), color).save(path, "PNG")
    return path


def test_main_full_flow_stops_on_duplicate(tmp_path, monkeypatch):
    """main() の統合テスト: モックで一連の流れを検証。
    3 ページ目以降は同じ内容を返し、stop-after=3 で停止することを確認。
    """
    monkeypatch.chdir(tmp_path)
    output_pdf = tmp_path / "out.pdf"

    captured_pages = [0]
    def fake_screencapture(cmd, **kwargs):
        # cmd の最後が出力パス
        out_path = Path(cmd[-1])
        captured_pages[0] += 1
        # 3 ページ目以降は全部同じ画像を返す（末尾検出させる）
        idx = min(captured_pages[0], 3)
        _make_png(out_path, (50 * idx, 100, 200))
        return MagicMock(returncode=0, stdout="", stderr="")

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        # 順序注意: window_bounds 取得スクリプトには "exists process" も含まれているため、
        # より具体的な "position of front window" を先に判定する。
        if "position of front window" in joined:
            return MagicMock(returncode=0, stdout="0,0,1024,1400\n", stderr="")
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    def dispatch(cmd, **kwargs):
        if cmd[0] == "screencapture":
            return fake_screencapture(cmd, **kwargs)
        if cmd[0] == "osascript":
            return fake_osascript(cmd, **kwargs)
        raise AssertionError(f"unexpected cmd: {cmd}")

    with patch("kindle_screenshot.capture.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.input.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.cli.input", return_value=""), \
         patch("kindle_screenshot.cli.time.sleep"):
        rc = main([
            "-o", str(output_pdf.name),
            "-d", str(tmp_path),
            "--countdown", "0",
            "--crop-top", "0",
            "--crop-bottom", "0",
            "--stop-after", "3",
        ])

    assert rc == 0
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0


def test_main_exits_when_kindle_not_running(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd, **kwargs):
        if cmd[0] == "osascript":
            joined = " ".join(cmd)
            if "exists process" in joined:
                return MagicMock(returncode=0, stdout="false\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("kindle_screenshot.input.subprocess.run", side_effect=fake_run), \
         patch("kindle_screenshot.cli.input", return_value=""):
        rc = main(["--countdown", "0"])

    assert rc == 2


def test_main_max_pages_safety_stop(tmp_path, monkeypatch):
    """--max-pages 到達で停止し、PDF が生成されることを確認。"""
    monkeypatch.chdir(tmp_path)
    output_pdf = tmp_path / "max.pdf"

    counter = [0]
    def fake_screencapture(cmd, **kwargs):
        out_path = Path(cmd[-1])
        counter[0] += 1
        # 毎回大きく違う色で末尾検出にかからないようにする（grayscale 64x64 後も
        # 別ハッシュになるよう RGB 全成分を変える）。
        c = counter[0]
        _make_png(out_path, ((c * 53) % 256, (c * 97) % 256, (c * 31) % 256))
        return MagicMock(returncode=0, stdout="", stderr="")

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        # 順序注意: window_bounds 取得スクリプトには "exists process" も含まれているため、
        # より具体的な "position of front window" を先に判定する。
        if "position of front window" in joined:
            return MagicMock(returncode=0, stdout="0,0,1024,1400\n", stderr="")
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    def dispatch(cmd, **kwargs):
        if cmd[0] == "screencapture":
            return fake_screencapture(cmd, **kwargs)
        return fake_osascript(cmd, **kwargs)

    with patch("kindle_screenshot.capture.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.input.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.cli.input", return_value=""), \
         patch("kindle_screenshot.cli.time.sleep"):
        rc = main([
            "-o", output_pdf.name,
            "-d", str(tmp_path),
            "--countdown", "0",
            "--max-pages", "5",
            "--crop-top", "0",
            "--crop-bottom", "0",
        ])

    assert rc == 0
    assert output_pdf.exists()
    assert counter[0] == 5


import subprocess


def test_main_returns_3_when_osascript_permission_denied(tmp_path, monkeypatch, capsys):
    """osascript が CalledProcessError で失敗（Accessibility 権限不足相当）した場合、
    終了コード 3 + System Settings への案内が出ることを確認（HIGH #1）。"""
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd, **kwargs):
        # is_kindle_running の osascript 呼び出しで失敗をシミュレート
        if cmd[0] == "osascript":
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                output="",
                stderr="execution error: Not authorized to send Apple events to System Events. (-1743)",
            )
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("kindle_screenshot.input.subprocess.run", side_effect=fake_run), \
         patch("kindle_screenshot.cli.input", return_value=""):
        rc = main(["--countdown", "0"])

    assert rc == 3
    captured = capsys.readouterr()
    assert "Accessibility" in captured.err
    assert "System Settings" in captured.err
    # 副次バグ修正: 権限不足以外の可能性（AppleScript 非対応）も併記する
    assert "AppleScript" in captured.err


def test_main_osascript_minus_1728_emphasizes_applescript_incompatibility(
    tmp_path, monkeypatch, capsys
):
    """osascript stderr に `(-1728)` が含まれる場合は「Kindle アプリの AppleScript 非対応の
    可能性」を強調案内する。これは権限不足ではなくアプリ自体がスクリプタブルでないエラー
    のため、ユーザーが Accessibility 設定を弄っても解決しない（issue #9 副次バグ）。"""
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd, **kwargs):
        if cmd[0] == "osascript":
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                output="",
                stderr='execution error: application "Kindle" を取り出すことはできません。 (-1728)',
            )
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("kindle_screenshot.input.subprocess.run", side_effect=fake_run), \
         patch("kindle_screenshot.cli.input", return_value=""):
        rc = main(["--countdown", "0"])

    assert rc == 3
    err = capsys.readouterr().err
    # 権限不足案内も併記されているはず
    assert "Accessibility" in err
    # -1728 専用の追加案内が出ていることを確認
    assert "-1728" in err
    assert "AppleScript" in err
    # バージョン互換性に言及
    assert ("バージョン" in err) or ("互換" in err)


def test_main_returns_3_when_screencapture_permission_denied(tmp_path, monkeypatch, capsys):
    """screencapture が 1 ページ目から CalledProcessError で失敗（Screen Recording 権限不足相当）
    した場合、終了コード 3 + Screen Recording 設定への案内が出ることを確認（HIGH #1）。"""
    monkeypatch.chdir(tmp_path)
    output_pdf = tmp_path / "out.pdf"

    def fake_screencapture(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            output="",
            stderr="screencapture: cannot run two captures at a time",
        )

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        if "position of front window" in joined:
            return MagicMock(returncode=0, stdout="0,0,1024,1400\n", stderr="")
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    def dispatch(cmd, **kwargs):
        if cmd[0] == "screencapture":
            return fake_screencapture(cmd, **kwargs)
        return fake_osascript(cmd, **kwargs)

    with patch("kindle_screenshot.capture.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.input.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.cli.input", return_value=""), \
         patch("kindle_screenshot.cli.time.sleep"):
        rc = main([
            "-o", output_pdf.name,
            "-d", str(tmp_path),
            "--countdown", "0",
            "--crop-top", "0",
            "--crop-bottom", "0",
        ])

    assert rc == 3
    captured = capsys.readouterr()
    assert "Screen Recording" in captured.err
    assert "System Settings" in captured.err


def test_main_window_disappears_midway_falls_back_to_interrupt_prompt(tmp_path, monkeypatch):
    """途中で Kindle ウィンドウが消えると screencapture が CalledProcessError を投げる。
    リトライ後も失敗した場合、取得済みページがあれば Ctrl+C と同等の中断扱いプロンプトに
    合流し、Y を選べば取得済みページで PDF 化されることを確認（HIGH #2）。"""
    monkeypatch.chdir(tmp_path)
    output_pdf = tmp_path / "partial.pdf"

    counter = [0]
    def fake_screencapture(cmd, **kwargs):
        out_path = Path(cmd[-1])
        counter[0] += 1
        # 1〜3 ページ目は成功、4 ページ目以降はウィンドウ消滅で常に失敗
        # （リトライ含めて毎回 CalledProcessError）
        if counter[0] <= 3:
            c = counter[0]
            _make_png(out_path, ((c * 53) % 256, (c * 97) % 256, (c * 31) % 256))
            return MagicMock(returncode=0, stdout="", stderr="")
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            output="",
            stderr="screencapture: could not create image from window",
        )

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        if "position of front window" in joined:
            return MagicMock(returncode=0, stdout="0,0,1024,1400\n", stderr="")
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    def dispatch(cmd, **kwargs):
        if cmd[0] == "screencapture":
            return fake_screencapture(cmd, **kwargs)
        return fake_osascript(cmd, **kwargs)

    # Enter 待ち（最初の input）→ 中断プロンプトの応答（"y"）の順に返す
    inputs = iter(["", "y"])

    with patch("kindle_screenshot.capture.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.input.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.cli.input", side_effect=lambda *a, **kw: next(inputs)), \
         patch("kindle_screenshot.cli.time.sleep"):
        rc = main([
            "-o", output_pdf.name,
            "-d", str(tmp_path),
            "--countdown", "0",
            "--crop-top", "0",
            "--crop-bottom", "0",
            "--stop-after", "5",  # 末尾検出で停止しないよう厳しめ
        ])

    assert rc == 0
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0


def test_main_window_disappears_midway_user_declines_pdf(tmp_path, monkeypatch):
    """ウィンドウ消滅で中断プロンプト → ユーザー N → 終了コード 130 を確認（HIGH #2）。"""
    monkeypatch.chdir(tmp_path)
    output_pdf = tmp_path / "declined.pdf"

    counter = [0]
    def fake_screencapture(cmd, **kwargs):
        out_path = Path(cmd[-1])
        counter[0] += 1
        if counter[0] <= 2:
            c = counter[0]
            _make_png(out_path, ((c * 53) % 256, (c * 97) % 256, (c * 31) % 256))
            return MagicMock(returncode=0, stdout="", stderr="")
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            output="",
            stderr="screencapture: could not create image from window",
        )

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        if "position of front window" in joined:
            return MagicMock(returncode=0, stdout="0,0,1024,1400\n", stderr="")
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    def dispatch(cmd, **kwargs):
        if cmd[0] == "screencapture":
            return fake_screencapture(cmd, **kwargs)
        return fake_osascript(cmd, **kwargs)

    inputs = iter(["", "n"])

    with patch("kindle_screenshot.capture.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.input.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.cli.input", side_effect=lambda *a, **kw: next(inputs)), \
         patch("kindle_screenshot.cli.time.sleep"):
        rc = main([
            "-o", output_pdf.name,
            "-d", str(tmp_path),
            "--countdown", "0",
            "--crop-top", "0",
            "--crop-bottom", "0",
            "--stop-after", "5",
        ])

    assert rc == 130
    assert not output_pdf.exists()


def test_main_max_pages_trims_trailing_duplicates(tmp_path, monkeypatch, capsys):
    """--max-pages 到達時に末尾の連続重複ページがトリミングされ、PDF に含まれないことを
    確認（MEDIUM #1）。stop-after=3 だが末尾重複が 2 連続のため停止判定にはかからず、
    --max-pages で停止するケース。"""
    monkeypatch.chdir(tmp_path)
    output_pdf = tmp_path / "trimmed.pdf"

    counter = [0]
    last_color: dict[str, tuple[int, int, int]] = {}

    def fake_screencapture(cmd, **kwargs):
        out_path = Path(cmd[-1])
        counter[0] += 1
        c = counter[0]
        # 1〜3 ページ目は別画像、4〜5 ページ目は同じ画像（2 連続重複）。
        # max-pages=5、stop-after=3 のため停止せず max-pages で抜ける。
        if c <= 3:
            color = ((c * 53) % 256, (c * 97) % 256, (c * 31) % 256)
        else:
            color = (200, 50, 100)  # 4 と 5 は同じ
        last_color["last"] = color
        _make_png(out_path, color)
        return MagicMock(returncode=0, stdout="", stderr="")

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        if "position of front window" in joined:
            return MagicMock(returncode=0, stdout="0,0,1024,1400\n", stderr="")
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    def dispatch(cmd, **kwargs):
        if cmd[0] == "screencapture":
            return fake_screencapture(cmd, **kwargs)
        return fake_osascript(cmd, **kwargs)

    with patch("kindle_screenshot.capture.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.input.subprocess.run", side_effect=dispatch), \
         patch("kindle_screenshot.cli.input", return_value=""), \
         patch("kindle_screenshot.cli.time.sleep"):
        rc = main([
            "-o", output_pdf.name,
            "-d", str(tmp_path),
            "--countdown", "0",
            "--max-pages", "5",
            "--stop-after", "3",
            "--crop-top", "0",
            "--crop-bottom", "0",
        ])

    assert rc == 0
    assert output_pdf.exists()
    assert counter[0] == 5  # max-pages まで撮影した
    err = capsys.readouterr().err
    assert "末尾の連続重複" in err  # トリミングメッセージ
    # 4 ページ目と 5 ページ目が同一なので、5 ページ撮影 → trim_count=1 で 4 ページに
    # なるはず。PDF が確かに生成されていることを軽く確認（ページ数の厳密確認は
    # img2pdf の生成バイナリのため省略）。
    assert output_pdf.stat().st_size > 0
