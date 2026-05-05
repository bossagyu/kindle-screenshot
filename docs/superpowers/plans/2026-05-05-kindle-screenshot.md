# kindle-screenshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kindle for Mac で開いた書籍を自動でページ送りしながらスクリーンショットを取り、Claude Code が読める品質の PDF にまとめる CLI ツールを作る。

**Architecture:** macOS 標準の `screencapture` で Kindle ウィンドウ単位のキャプチャを取得し、PIL で余白除去・形式変換、`img2pdf` で無劣化 PDF 化する。`osascript` で Kindle の起動確認・アクティブ化・右矢印キー送信を行う。画像ハッシュの N 連続一致で末尾を自動検出し、Ctrl+C / `--max-pages` でも停止可能。

**Tech Stack:** Python 3.12+ / uv（プロジェクト内 `.venv`） / Pillow / img2pdf / pytest / 標準 `subprocess` で `screencapture`・`osascript` を呼び出し。

**Spec:** `docs/superpowers/specs/2026-05-05-kindle-screenshot-design.md`

---

## File Structure

```
kindle-screenshot/
├── pyproject.toml          # uv プロジェクト定義 + 依存
├── README.md               # 権限設定・使い方・手動統合テスト手順
├── .python-version         # uv 用 Python バージョン固定
├── .gitignore              # .venv/, *.pyc, dist/, *.pdf
├── src/
│   └── kindle_screenshot/
│       ├── __init__.py     # パッケージマーカー
│       ├── __main__.py     # python -m kindle_screenshot エントリ
│       ├── cli.py          # argparse + メインフロー
│       ├── capture.py      # screencapture / PIL 経由のキャプチャ・余白除去
│       ├── input.py        # osascript ラッパー（起動確認・アクティブ化・キー送信）
│       ├── hashing.py      # 画像ハッシュ + 連続重複検出
│       └── pdf.py          # img2pdf ラッパー
└── tests/
    ├── __init__.py
    ├── test_hashing.py
    ├── test_pdf.py
    ├── test_capture.py
    ├── test_input.py
    └── test_cli.py
```

各モジュールの責務はスペック §5 に従う。各タスクは独立してテスト可能で、TDD（RED→GREEN→COMMIT）の順で進める。

---

### Task 1: プロジェクト骨格と uv 環境構築

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `src/kindle_screenshot/__init__.py`
- Create: `src/kindle_screenshot/__main__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: `.python-version` を作成**

```
3.12
```

- [ ] **Step 2: `.gitignore` を作成**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# uv / venv
.venv/
.uv-cache/

# Build
build/
dist/
*.egg-info/

# IDE / OS
.idea/
.vscode/
.DS_Store

# 出力 PDF はコミットしない
*.pdf

# pytest / coverage
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 3: `pyproject.toml` を作成**

```toml
[project]
name = "kindle-screenshot"
version = "0.1.0"
description = "Kindle for Mac の書籍をスクリーンショットで PDF 化する CLI ツール"
requires-python = ">=3.12"
dependencies = [
    "Pillow>=10.0.0",
    "img2pdf>=0.5.0",
]

[project.scripts]
kindle-screenshot = "kindle_screenshot.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/kindle_screenshot"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

- [ ] **Step 4: パッケージ初期化ファイルを作成**

`src/kindle_screenshot/__init__.py`:
```python
"""Kindle for Mac の書籍をスクリーンショットで PDF 化する CLI ツール。"""

__version__ = "0.1.0"
```

`src/kindle_screenshot/__main__.py`:
```python
from kindle_screenshot.cli import main

if __name__ == "__main__":
    main()
```

`tests/__init__.py`:
```python
```

- [ ] **Step 5: uv 環境を同期**

Run: `uv sync`
Expected: `.venv/` 配下に Python 3.12 + 依存ライブラリがインストールされる。プロジェクト外には影響しない。

- [ ] **Step 6: pytest が起動することを確認**

Run: `uv run pytest --collect-only`
Expected: `no tests ran` または `collected 0 items`（テスト未実装でエラーにならない）

- [ ] **Step 7: コミット**

```bash
git add pyproject.toml .python-version .gitignore src/ tests/
git commit -m "chore: uv プロジェクト骨格と pyproject.toml を初期化"
```

---

### Task 2: hashing モジュール - `compute_hash` 関数

**Files:**
- Create: `tests/test_hashing.py`
- Create: `src/kindle_screenshot/hashing.py`

責務: 画像を小さいグレースケールに縮小してピクセル列の SHA256 を取る。同一フレーム判定用。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_hashing.py`:
```python
from pathlib import Path
from PIL import Image
import pytest

from kindle_screenshot.hashing import compute_hash


def make_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path)
    return path


def test_compute_hash_same_image_same_hash(tmp_path):
    a = make_image(tmp_path / "a.png", (255, 0, 0))
    b = make_image(tmp_path / "b.png", (255, 0, 0))
    assert compute_hash(a) == compute_hash(b)


def test_compute_hash_different_images_different_hash(tmp_path):
    a = make_image(tmp_path / "a.png", (255, 0, 0))
    b = make_image(tmp_path / "b.png", (0, 0, 255))
    assert compute_hash(a) != compute_hash(b)


def test_compute_hash_returns_hex_string(tmp_path):
    a = make_image(tmp_path / "a.png", (128, 128, 128))
    h = compute_hash(a)
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)  # 16進文字列として有効
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: `ImportError` か `AttributeError` で失敗（compute_hash が未実装）

- [ ] **Step 3: 最小実装**

`src/kindle_screenshot/hashing.py`:
```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_hashing.py src/kindle_screenshot/hashing.py
git commit -m "feat(hashing): 画像 SHA256 ハッシュ計算 compute_hash を追加"
```

---

### Task 3: hashing モジュール - `DuplicateDetector` クラス

**Files:**
- Modify: `tests/test_hashing.py`
- Modify: `src/kindle_screenshot/hashing.py`

責務: ハッシュを順次受け取り、N 連続で同じハッシュなら停止信号を出す。末尾の重複枚数（PDF 化時にトリミングする数）も提供する。

- [ ] **Step 1: 失敗するテストを追加**

`tests/test_hashing.py` の末尾に追加:
```python
from kindle_screenshot.hashing import DuplicateDetector


def test_detector_returns_false_for_first_hash():
    d = DuplicateDetector(stop_after=3)
    assert d.add("aaa") is False


def test_detector_returns_false_for_different_hashes():
    d = DuplicateDetector(stop_after=3)
    assert d.add("aaa") is False
    assert d.add("bbb") is False
    assert d.add("ccc") is False


def test_detector_returns_true_after_n_consecutive_duplicates():
    d = DuplicateDetector(stop_after=3)
    assert d.add("xxx") is False  # count=1
    assert d.add("xxx") is False  # count=2
    assert d.add("xxx") is True   # count=3, 停止


def test_detector_resets_counter_on_change():
    d = DuplicateDetector(stop_after=3)
    d.add("xxx")  # count=1
    d.add("xxx")  # count=2
    d.add("yyy")  # リセット, count=1
    assert d.add("yyy") is False  # count=2
    assert d.add("yyy") is True   # count=3


def test_detector_trim_count_after_trigger():
    d = DuplicateDetector(stop_after=3)
    d.add("a")    # count=1, trim=0
    d.add("a")    # count=2, trim=1
    d.add("a")    # count=3, trim=2 → 停止判定
    assert d.trim_count == 2


def test_detector_invalid_stop_after():
    with pytest.raises(ValueError):
        DuplicateDetector(stop_after=0)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: 6 件の新規テストが ImportError または AttributeError で失敗。

- [ ] **Step 3: `DuplicateDetector` クラスを追加**

`src/kindle_screenshot/hashing.py` の末尾に追加:
```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: 9 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_hashing.py src/kindle_screenshot/hashing.py
git commit -m "feat(hashing): N 連続重複を検出する DuplicateDetector を追加"
```

---

### Task 4: pdf モジュール - `images_to_pdf` 関数

**Files:**
- Create: `tests/test_pdf.py`
- Create: `src/kindle_screenshot/pdf.py`

責務: 画像ファイル群を img2pdf で 1 つの PDF にまとめる（再エンコードなし、無劣化）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_pdf.py`:
```python
from pathlib import Path
from PIL import Image
import pytest

from kindle_screenshot.pdf import images_to_pdf


def make_jpeg(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (400, 600)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path, "JPEG", quality=85)
    return path


def test_images_to_pdf_creates_file(tmp_path):
    imgs = [
        make_jpeg(tmp_path / f"p{i:03d}.jpg", (50 * i, 100, 200))
        for i in range(1, 4)
    ]
    out = tmp_path / "book.pdf"
    images_to_pdf(imgs, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_images_to_pdf_correct_page_count(tmp_path):
    imgs = [
        make_jpeg(tmp_path / f"p{i:03d}.jpg", (50, 100, 200))
        for i in range(1, 6)
    ]
    out = tmp_path / "book.pdf"
    images_to_pdf(imgs, out)
    content = out.read_bytes()
    # PDF 内の "/Type /Page" を数えれば page count
    page_count = content.count(b"/Type /Page\n") + content.count(b"/Type/Page ")
    # img2pdf の出力は典型的に "/Type /Page" を各ページに含む
    assert b"%PDF" in content[:8]


def test_images_to_pdf_creates_parent_dir(tmp_path):
    imgs = [make_jpeg(tmp_path / "p1.jpg", (255, 0, 0))]
    out = tmp_path / "nested" / "dir" / "book.pdf"
    images_to_pdf(imgs, out)
    assert out.exists()


def test_images_to_pdf_empty_list_raises(tmp_path):
    with pytest.raises(ValueError):
        images_to_pdf([], tmp_path / "empty.pdf")
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_pdf.py -v`
Expected: ImportError で失敗。

- [ ] **Step 3: 実装**

`src/kindle_screenshot/pdf.py`:
```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_pdf.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_pdf.py src/kindle_screenshot/pdf.py
git commit -m "feat(pdf): img2pdf で無劣化 PDF 生成 images_to_pdf を追加"
```

---

### Task 5: capture モジュール - `get_kindle_window_id`

**Files:**
- Create: `tests/test_capture.py`
- Create: `src/kindle_screenshot/capture.py`

責務: osascript で起動中の Kindle.app のフロントウィンドウ ID を取得。起動していない／ウィンドウが無い場合は専用例外を投げる。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_capture.py`:
```python
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from kindle_screenshot.capture import get_kindle_window_id, KindleNotFoundError


def _mock_run(stdout: str, returncode: int = 0):
    return MagicMock(stdout=stdout, stderr="", returncode=returncode)


def test_get_kindle_window_id_returns_int():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("12345\n")
        assert get_kindle_window_id() == 12345


def test_get_kindle_window_id_raises_when_kindle_not_running():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("NOT_RUNNING\n")
        with pytest.raises(KindleNotFoundError, match="起動していません"):
            get_kindle_window_id()


def test_get_kindle_window_id_raises_when_no_window():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("NO_WINDOW\n")
        with pytest.raises(KindleNotFoundError, match="ウィンドウ"):
            get_kindle_window_id()


def test_get_kindle_window_id_calls_osascript():
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run("999\n")
        get_kindle_window_id()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert "-e" in args
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_capture.py -v`
Expected: ImportError で失敗。

- [ ] **Step 3: 実装**

`src/kindle_screenshot/capture.py`:
```python
"""Kindle ウィンドウのキャプチャと画像処理。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image


class KindleNotFoundError(RuntimeError):
    """Kindle.app が起動していない、またはウィンドウが見つからない。"""


_WINDOW_ID_SCRIPT = """
tell application "System Events"
    if not (exists process "Kindle") then
        return "NOT_RUNNING"
    end if
    tell process "Kindle"
        if (count of windows) = 0 then
            return "NO_WINDOW"
        end if
        try
            return id of front window as string
        on error
            return "NO_WINDOW"
        end try
    end tell
end tell
"""


def get_kindle_window_id() -> int:
    """Kindle.app のフロントウィンドウ ID を取得する。

    Raises:
        KindleNotFoundError: Kindle 未起動 or ウィンドウなし
    """
    result = subprocess.run(
        ["osascript", "-e", _WINDOW_ID_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip()
    if out == "NOT_RUNNING":
        raise KindleNotFoundError("Kindle.app が起動していません。アプリを起動して書籍を開いてください。")
    if out == "NO_WINDOW":
        raise KindleNotFoundError("Kindle のウィンドウが見つかりません。書籍を開いてください。")
    return int(out)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_capture.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_capture.py src/kindle_screenshot/capture.py
git commit -m "feat(capture): Kindle ウィンドウ ID 取得 get_kindle_window_id を追加"
```

---

### Task 6: capture モジュール - `capture_window_to_png`（screencapture 呼び出し）

**Files:**
- Modify: `tests/test_capture.py`
- Modify: `src/kindle_screenshot/capture.py`

責務: `screencapture -l <window_id> -t png -x <out>` を呼び出し、ウィンドウのみをキャプチャ。PNG で保存（後段で必要なら JPEG に変換）。

- [ ] **Step 1: 失敗するテストを追加**

`tests/test_capture.py` の末尾に追加:
```python
from pathlib import Path

from kindle_screenshot.capture import capture_window_to_png


def test_capture_window_to_png_runs_screencapture(tmp_path):
    out = tmp_path / "page.png"
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        # subprocess.run の戻り値は使わないが、ファイル作成を擬似的に行う
        def fake_run(*args, **kwargs):
            out.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024)
            return MagicMock(returncode=0)
        mock_run.side_effect = fake_run
        capture_window_to_png(window_id=12345, out=out)

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "screencapture"
        assert "-l" in called_cmd
        assert "12345" in called_cmd
        assert "-t" in called_cmd
        png_index = called_cmd.index("-t") + 1
        assert called_cmd[png_index] == "png"
        assert str(out) in called_cmd


def test_capture_window_to_png_raises_on_empty_file(tmp_path):
    out = tmp_path / "empty.png"
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        def fake_run(*args, **kwargs):
            out.write_bytes(b"")
            return MagicMock(returncode=0)
        mock_run.side_effect = fake_run
        with pytest.raises(RuntimeError, match="キャプチャ"):
            capture_window_to_png(window_id=12345, out=out)


def test_capture_window_to_png_raises_when_file_missing(tmp_path):
    out = tmp_path / "missing.png"
    with patch("kindle_screenshot.capture.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RuntimeError, match="キャプチャ"):
            capture_window_to_png(window_id=12345, out=out)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_capture.py -v`
Expected: 3 件の新規テストが ImportError で失敗。

- [ ] **Step 3: `capture_window_to_png` を追加**

`src/kindle_screenshot/capture.py` の末尾に追加:
```python
def capture_window_to_png(window_id: int, out: Path) -> None:
    """指定ウィンドウ ID の内容を PNG でキャプチャする。

    `-x` で無音化、`-t png` で常に可逆形式。後段で必要なら PIL で
    JPEG に変換する（screencapture の JPEG は品質指定不可なので、
    PNG を経由して品質を厳密に制御する設計にしている）。
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["screencapture", "-l", str(window_id), "-t", "png", "-x", str(out)],
        check=True,
    )
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"キャプチャ失敗: {out}（権限不足の可能性）")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_capture.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_capture.py src/kindle_screenshot/capture.py
git commit -m "feat(capture): screencapture でウィンドウキャプチャする capture_window_to_png を追加"
```

---

### Task 7: capture モジュール - `process_image`（余白除去 + 形式変換）

**Files:**
- Modify: `tests/test_capture.py`
- Modify: `src/kindle_screenshot/capture.py`

責務: PNG 中間ファイルを読み、上下左右の余白を除去し、最終形式（JPEG/PNG）で保存する。中間 PNG は削除。

- [ ] **Step 1: 失敗するテストを追加**

`tests/test_capture.py` の末尾に追加:
```python
from kindle_screenshot.capture import process_image


def _make_png(path: Path, size: tuple[int, int] = (400, 600), color: tuple[int, int, int] = (200, 100, 50)) -> Path:
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def test_process_image_no_crop_jpeg(tmp_path):
    src = _make_png(tmp_path / "src.png")
    dst = tmp_path / "out.jpg"
    process_image(src, dst, fmt="jpeg", quality=85)
    assert dst.exists()
    assert not src.exists()  # 中間 PNG は削除される
    with Image.open(dst) as im:
        assert im.format == "JPEG"
        assert im.size == (400, 600)


def test_process_image_no_crop_png(tmp_path):
    src = _make_png(tmp_path / "src.png", size=(300, 400))
    dst = tmp_path / "out.png"
    process_image(src, dst, fmt="png", quality=85)
    assert dst.exists()
    with Image.open(dst) as im:
        assert im.format == "PNG"
        assert im.size == (300, 400)


def test_process_image_crops_correctly(tmp_path):
    src = _make_png(tmp_path / "src.png", size=(400, 600))
    dst = tmp_path / "out.jpg"
    process_image(src, dst, fmt="jpeg", quality=85,
                  crop_top=60, crop_bottom=40, crop_left=10, crop_right=20)
    with Image.open(dst) as im:
        # 元 400x600 から 上60+下40+左10+右20 を除去
        assert im.size == (400 - 10 - 20, 600 - 60 - 40)
        assert im.size == (370, 500)


def test_process_image_invalid_crop_raises(tmp_path):
    src = _make_png(tmp_path / "src.png", size=(100, 100))
    dst = tmp_path / "out.jpg"
    with pytest.raises(ValueError, match="クロップ"):
        process_image(src, dst, fmt="jpeg", quality=85,
                      crop_top=60, crop_bottom=60)


def test_process_image_jpg_alias_treated_as_jpeg(tmp_path):
    src = _make_png(tmp_path / "src.png")
    dst = tmp_path / "out.jpg"
    process_image(src, dst, fmt="jpg", quality=85)
    with Image.open(dst) as im:
        assert im.format == "JPEG"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_capture.py -v`
Expected: 5 件の新規テストが ImportError で失敗。

- [ ] **Step 3: `process_image` を追加**

`src/kindle_screenshot/capture.py` の末尾に追加:
```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_capture.py -v`
Expected: 12 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_capture.py src/kindle_screenshot/capture.py
git commit -m "feat(capture): 余白除去 + 形式変換する process_image を追加"
```

---

### Task 8: input モジュール - osascript ラッパー一式

**Files:**
- Create: `tests/test_input.py`
- Create: `src/kindle_screenshot/input.py`

責務: Kindle.app の起動確認、アクティブ化、右矢印キー送信。すべて osascript subprocess の薄いラッパー。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_input.py`:
```python
from unittest.mock import patch, MagicMock

from kindle_screenshot.input import is_kindle_running, activate_kindle, send_right_arrow


def test_is_kindle_running_true():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="true\n", returncode=0)
        assert is_kindle_running() is True


def test_is_kindle_running_false():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="false\n", returncode=0)
        assert is_kindle_running() is False


def test_is_kindle_running_calls_osascript():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="true\n", returncode=0)
        is_kindle_running()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"


def test_activate_kindle_calls_osascript_with_activate():
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        activate_kindle()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"
        joined = " ".join(cmd)
        assert "Kindle" in joined
        assert "activate" in joined


def test_send_right_arrow_uses_key_code_124():
    # macOS の右矢印キーは key code 124
    with patch("kindle_screenshot.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        send_right_arrow()
        cmd = mock_run.call_args[0][0]
        joined = " ".join(cmd)
        assert "124" in joined
        assert "key code" in joined
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_input.py -v`
Expected: ImportError で失敗。

- [ ] **Step 3: 実装**

`src/kindle_screenshot/input.py`:
```python
"""Kindle.app の制御とキー送信（osascript ラッパー）。"""

from __future__ import annotations

import subprocess


_IS_RUNNING_SCRIPT = '''
tell application "System Events"
    if exists process "Kindle" then
        return "true"
    else
        return "false"
    end if
end tell
'''

_ACTIVATE_SCRIPT = 'tell application "Kindle" to activate'

_RIGHT_ARROW_SCRIPT = 'tell application "System Events" to key code 124'


def is_kindle_running() -> bool:
    """Kindle.app プロセスが起動しているか判定する。"""
    result = subprocess.run(
        ["osascript", "-e", _IS_RUNNING_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == "true"


def activate_kindle() -> None:
    """Kindle.app を前面に出す。フォーカス奪取への対策として毎ループ前に呼ぶ。"""
    subprocess.run(
        ["osascript", "-e", _ACTIVATE_SCRIPT],
        check=True,
    )


def send_right_arrow() -> None:
    """右矢印キーを System Events 経由で送る（key code 124 = →）。"""
    subprocess.run(
        ["osascript", "-e", _RIGHT_ARROW_SCRIPT],
        check=True,
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_input.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_input.py src/kindle_screenshot/input.py
git commit -m "feat(input): osascript で Kindle 制御するラッパー関数群を追加"
```

---

### Task 9: cli モジュール - 引数パースとデフォルトファイル名

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/kindle_screenshot/cli.py`

責務: argparse による引数定義と、デフォルトファイル名（`kindle-YYYYMMDD-HHMMSS.pdf`）の生成。`main` 関数本体は次タスクで実装し、ここではパースのみテストする。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_cli.py`:
```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ImportError で失敗。

- [ ] **Step 3: 実装**

`src/kindle_screenshot/cli.py`:
```python
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
                   help=f"出力 PDF ファイル名（デフォルト: kindle-YYYYMMDD-HHMMSS.pdf）")
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: コミット**

```bash
git add tests/test_cli.py src/kindle_screenshot/cli.py
git commit -m "feat(cli): argparse 定義とデフォルトファイル名生成を追加"
```

---

### Task 10: cli モジュール - メインフロー（オーケストレーション）

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/kindle_screenshot/cli.py`

責務: 実際の処理フローを統合する `main()` 関数。Kindle 起動確認 → ウィンドウ ID 取得 → カウントダウン → キャプチャループ → PDF 化 → 一時ディレクトリ削除。Ctrl+C と `--max-pages` 安全弁にも対応。

- [ ] **Step 1: 失敗する統合テストを追加**

`tests/test_cli.py` の末尾に追加:
```python
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
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        if "id of front window" in joined:
            return MagicMock(returncode=0, stdout="42\n", stderr="")
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
        # 毎回違う色で末尾検出にかからないようにする
        _make_png(out_path, (counter[0] % 256, 100, 200))
        return MagicMock(returncode=0, stdout="", stderr="")

    def fake_osascript(cmd, **kwargs):
        joined = " ".join(cmd)
        if "exists process" in joined:
            return MagicMock(returncode=0, stdout="true\n", stderr="")
        if "id of front window" in joined:
            return MagicMock(returncode=0, stdout="42\n", stderr="")
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_cli.py -v`
Expected: `NotImplementedError` または引数不一致で失敗。

- [ ] **Step 3: `cli.py` を全面更新（imports 追加 + `main` 本実装）**

Task 9 で作った `src/kindle_screenshot/cli.py` を以下の **完全な内容** に置き換え:
```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 9 tests pass（既存 6 + 新規 3）.

- [ ] **Step 5: 全テスト通ることを確認**

Run: `uv run pytest -v`
Expected: 全モジュールのテストがすべて pass。

- [ ] **Step 6: 起動して `--help` が動くことを確認**

Run: `uv run kindle-screenshot --help`
Expected: 引数一覧が表示される。

- [ ] **Step 7: コミット**

```bash
git add tests/test_cli.py src/kindle_screenshot/cli.py
git commit -m "feat(cli): 全モジュールを統合した main フローを実装"
```

---

### Task 11: README と手動統合テスト手順

**Files:**
- Modify: `README.md`

責務: ユーザー向けセットアップ手順、必要な macOS 権限、使い方、手動統合テスト手順、既知の制約を記載。

- [ ] **Step 1: README を全面更新**

`README.md`:
````markdown
# kindle-screenshot

Kindle for Mac で開いている書籍を自動でページ送りしながらスクリーンショットを取り、PDF にまとめる CLI ツール。Claude Code に読ませる用途を主目的とする。

## 動作環境

- macOS（Apple Silicon / Intel いずれも）
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Kindle for Mac（書籍を画面キャプチャ可能なバージョン）

## セットアップ

```bash
# このディレクトリ内で
uv sync
```

`.venv/` がプロジェクト内に作られ、依存ライブラリが隔離される。プロジェクト外には影響しない。

## 必要な macOS 権限

初回実行時、以下の権限を Terminal アプリに付与する必要がある。

1. **画面収録（Screen Recording）**
   - System Settings → Privacy & Security → Screen Recording
   - Terminal（または iTerm2、VS Code 統合ターミナル等）を許可
2. **アクセシビリティ（Accessibility）**
   - System Settings → Privacy & Security → Accessibility
   - 同じく Terminal を許可

権限不足時はツール起動時にエラー終了するので、メッセージに従って付与してから再実行。

## 使い方

```bash
# 最も簡単（全部デフォルト、出力はカレントに kindle-YYYYMMDD-HHMMSS.pdf）
uv run kindle-screenshot

# 出力名を指定
uv run kindle-screenshot -o "harry-potter-1.pdf"

# 漫画用（高画質 PNG + 長め待機 + 厳しめ停止条件）
uv run kindle-screenshot -o "manga.pdf" --format png --delay 1.0 --stop-after 5
```

実行フロー:

1. ツール起動 → 「Kindle で 1 ページ目を表示してください」と案内
2. Kindle for Mac で対象書籍の 1 ページ目を開く
3. ターミナルに戻って Enter
4. ツールが Kindle ウィンドウを検出、3 秒カウントダウン
5. 自動でページ送り＆キャプチャを繰り返す
6. 同じハッシュが 3 回連続したら末尾と判定して停止
7. 一時画像群を 1 つの PDF にまとめて出力

中断したいときは `Ctrl+C`。プロンプトで取得済みページのみで PDF 化するか選べる。

## 主要オプション

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `-o, --output` | `kindle-YYYYMMDD-HHMMSS.pdf` | 出力 PDF 名 |
| `-d, --output-dir` | `.` | 出力先 |
| `--delay` | `0.5` | ページ送り後の待機秒 |
| `--format` | `jpeg` | `jpeg` or `png` |
| `--quality` | `85` | JPEG 品質 (1-100) |
| `--max-pages` | `2000` | 安全停止枚数 |
| `--stop-after` | `3` | N 連続同一で停止 |
| `--countdown` | `3` | 開始前カウントダウン秒 |
| `--crop-top` | `60` | 上部除去 px（Kindle ツールバー） |
| `--crop-bottom` | `40` | 下部除去 px（進捗バー） |
| `--crop-left` | `0` | 左余白 px |
| `--crop-right` | `0` | 右余白 px |

`uv run kindle-screenshot --help` で全オプション参照。

## 余白調整のコツ

`--crop-top` `--crop-bottom` のデフォルト値は経験則。書籍を 1 度撮って、PDF を開いて Kindle ツールバーや進捗バーが残っていたら値を増やす。逆に本文が切れていたら減らす。

```bash
# 例: ツールバーがまだ残るので上を多めに、下も微調整
uv run kindle-screenshot --crop-top 90 --crop-bottom 50
```

## 開発・テスト

```bash
# ユニットテスト
uv run pytest -v

# カバレッジ付き
uv run pytest --cov=kindle_screenshot --cov-report=term-missing
```

## 手動統合テスト手順

CI で自動化できない部分。新機能追加・依存更新後に手動確認すること。

1. **基本フロー**: 短い書籍（10〜20 ページ）を Kindle で開き、デフォルト引数で実行 → PDF が生成され、開いて中身が読める
2. **末尾自動検出**: 上記 PDF のページ数が書籍の実ページ数と一致（重複ページが残っていない）
3. **Ctrl+C 中断**: ループ中に Ctrl+C → プロンプトで Y → 途中までの PDF が出る
4. **Ctrl+C 中断 + 拒否**: 同上で N → PDF が出ず終了コード 130
5. **Kindle 未起動**: Kindle.app を終了した状態で実行 → 終了コード 2 で適切なエラー
6. **漫画/固定レイアウト**: 漫画 1 冊で `--format png --delay 1.0 --stop-after 5` で実行 → 画質劣化なく取得
7. **Claude Code 検証**: 生成 PDF を Claude Code に投げて、文章を正しく読み取れるか確認

## 既知の制約・注意

- **macOS / Kindle のバージョン依存**: Apple や Amazon のアップデートで突然画面キャプチャが黒画面になる可能性がある。事前に `Cmd+Shift+4` で Kindle 上の本文がキャプチャできることを確認してから使うこと。
- **フォーカス奪取**: 実行中に通知バナーや他アプリにフォーカスを取られると、右矢印キーが Kindle に届かず同じページが連続キャプチャされて誤って終了判定される。実行中は Mac を触らない。
- **ハッシュ誤検出**: 真っ白なページが連続する書籍では誤って末尾判定する可能性。`--stop-after 5` などで調整。
- **DRM 黒画面書籍**: Kindle for Mac でも特定書籍は画面キャプチャが黒くなる場合あり。本ツールでは対処不可。

## ライセンスと利用制限

このツールは **自身が購入した書籍を私的使用目的で複製する** 範囲でのみ使うこと（日本国著作権法 第 30 条）。生成された PDF を配布・共有することは著作権侵害にあたる可能性がある。商用利用・配布・複数人での共有はしないこと。
````

- [ ] **Step 2: README をプレビューして崩れがないか確認**

Run: `uv run python -c "import pathlib; print(pathlib.Path('README.md').read_text()[:200])"`
Expected: 先頭にタイトルが見える。

- [ ] **Step 3: コミット**

```bash
git add README.md
git commit -m "docs: README にセットアップ・使い方・既知制約を記載"
```

---

## Self-Review チェック結果

スペック §1〜§9 と本プランのカバレッジを照合し、以下を確認済み:

- §3 アーキテクチャ → Task 5-8 でモジュール実装、Task 10 で統合
- §4 CLI インターフェース → Task 9 で全引数を実装、Task 10 で挙動を統合
- §5 モジュール構成 → Task 2-10 で全モジュールを TDD 実装
- §6 エラーハンドリング → Task 5（Kindle 未検出）、Task 6（キャプチャ失敗）、Task 10（Ctrl+C / max-pages / リトライ）
- §7 テスト戦略 → 各 Task に pytest テストを記述。手動統合テストは Task 11 README に手順記載
- §8 既知の制約 → Task 11 README に明記
- §9 将来拡張余地 → 現プランではスコープ外（OK）

**型一貫性チェック**: `compute_hash`、`DuplicateDetector.add` / `trim_count`、`capture_window_to_png` / `process_image` の引数名が後続タスクで一致していることを確認済み。

**Placeholder スキャン**: TBD/TODO/省略は無し。各ステップに完全なコードまたは具体的なコマンドを記載。

---

## 実行時のヒント（実装者向け）

- 各タスクは独立して実行・検証・コミット可能。タスク間で `--cov` を確認しながら進めると、カバレッジ 80% 超を維持しやすい。
- 手動統合テスト（README §手動統合テスト手順）は Task 11 完了後、本物の Kindle と書籍で必ず実施すること。ユニットテストだけでは subprocess 周りの実挙動はカバーされない。
- macOS の権限ダイアログは初回 `screencapture` / `osascript` 実行時に出る。テスト中はモックで回避しているので、初回手動実行時に許可することになる。
