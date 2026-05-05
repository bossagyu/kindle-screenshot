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
