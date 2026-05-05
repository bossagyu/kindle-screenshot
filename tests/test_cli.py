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
        # 順序注意: window_id 取得スクリプトには "exists process" も含まれているため、
        # より具体的な "id of front window" を先に判定する。
        if "id of front window" in joined:
            return MagicMock(returncode=0, stdout="42\n", stderr="")
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
        # 順序注意: window_id 取得スクリプトには "exists process" も含まれているため、
        # より具体的な "id of front window" を先に判定する。
        if "id of front window" in joined:
            return MagicMock(returncode=0, stdout="42\n", stderr="")
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
        if "id of front window" in joined:
            return MagicMock(returncode=0, stdout="42\n", stderr="")
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
