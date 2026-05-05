# kindle-screenshot 設計ドキュメント

- 作成日: 2026-05-05
- 作成者: kouhei
- ステータス: Draft

## 1. 目的

Kindle for Mac で開いている書籍を自動でページ送りしながらスクリーンショットを取り、PDF として保存する CLI ツール。

主用途は、生成された PDF を Claude Code（Vision）に読ませて内容を解析・要約・参照すること。人間が読む用途も副次的に想定するが、画質は Claude Vision が読める水準を最低保証とする。

## 2. スコープ

### 対象

- macOS で動作する Kindle for Mac デスクトップアプリで開かれた、ユーザー自身が購入済みの書籍。
- テキスト主体の書籍（小説・ビジネス書）と固定レイアウト書籍（漫画・図解書）の両方。
- 個人的・私的使用目的での複製のみ。

### 対象外

- Kindle Cloud Reader（ブラウザ版）への対応。本ツールはデスクトップアプリ専用。
- DRM 保護により Kindle for Mac でも画面キャプチャが黒画面になる書籍。事前にユーザーが手動の `Cmd+Shift+4` で本文がキャプチャ可能であることを確認している前提。
- 配布目的の複製、商用利用。

## 3. アーキテクチャ概要

### 技術スタック

| 項目 | 採用 |
|------|------|
| 言語 | Python 3.12+ |
| パッケージ管理 | uv（プロジェクト内 `.venv` を構築。プロジェクトディレクトリ外には影響を与えない） |
| 画像処理 | Pillow |
| PDF 生成 | img2pdf（無劣化、再エンコードなし） |
| キャプチャ | macOS 標準 `screencapture` コマンド（`subprocess` 経由） |
| 入力送信 / アプリ制御 | macOS 標準 `osascript` コマンド（`subprocess` 経由） |

外部 Python ライブラリは Pillow と img2pdf のみ。GUI 自動化用の追加依存（pyautogui 等）は使わない。

### 高レベルフロー

```
起動 → 引数パース
  → Kindle.app 起動確認
  → ユーザーに「Kindle で 1 ページ目を表示して Enter」と案内
  → Kindle のフロントウィンドウの位置(x,y)とサイズ(w,h)を取得
  → カウントダウン後、ループ開始:
       Kindle をアクティブ化（フォーカス奪取対策）
       右矢印キー送信（初回除く）
       --delay 秒待機
       ウィンドウ位置/サイズを指定して `screencapture -R x,y,w,h` でキャプチャ
       Pillow で上下左右の余白を除去
       直前画像とハッシュ比較
       --stop-after 連続同一 / Ctrl+C / --max-pages 到達 で停止
  → 一時画像群を img2pdf で PDF 化
  → 出力先に保存、一時ディレクトリ削除
```

> **補足（v0.1 → 修正版）**: 当初は `screencapture -l <window_id>` でウィンドウ ID 指定キャプチャを採用していたが、Kindle for Mac は AppleScript の `id of front window` プロパティに対応していない（`-1728` エラー）ことが手動統合テストで判明した。このため `position of front window` と `size of front window` を取得して `screencapture -R x,y,w,h` 方式に切り替えた（issue #7）。座標は論理ピクセル（ポイント）で、マルチディスプレイ環境では負の値も発生する。

### 必要な macOS 権限（初回のみユーザーが手動許可）

- Privacy & Security > Screen Recording — Terminal アプリに付与
- Privacy & Security > Accessibility — Terminal アプリに付与（osascript の System Events 経由のキー送信に必要）

権限が不足している場合、ツールはエラーメッセージで権限付与の手順を案内して終了する。

## 4. CLI インターフェース

### コマンド名

`kindle-screenshot`

uv 経由で `uv run kindle-screenshot ...` または `.venv` activate 後に直接実行。

### 引数

| オプション | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `-o, --output` | str | `kindle-YYYYMMDD-HHMMSS.pdf` | 出力 PDF ファイル名 |
| `-d, --output-dir` | path | カレントディレクトリ | 出力ディレクトリ |
| `--delay` | float | `0.5` | ページ送り後のキャプチャ前待機秒数 |
| `--format` | `jpeg` / `png` | `jpeg` | PDF 内画像形式 |
| `--quality` | int (1-100) | `85` | JPEG 品質（PNG 時は無視） |
| `--max-pages` | int | `2000` | 安全弁: この枚数で強制停止 |
| `--stop-after` | int | `3` | 同一ハッシュ N 連続で停止 |
| `--countdown` | int | `3` | ウィンドウ検出後、ループ開始までの秒数（ユーザーが Kindle 表示を確認する猶予） |
| `--crop-top` | int | `60` | ウィンドウ上部の Kindle ツールバー除去 px |
| `--crop-bottom` | int | `40` | ウィンドウ下部の進捗バー除去 px |
| `--crop-left` | int | `0` | 左余白 px |
| `--crop-right` | int | `0` | 右余白 px |
| `--keep-images` | path | なし | 指定ディレクトリに最終画像（`page_NNNNN.<jpg\|png>`）を保存。Claude Code への画像入力ワークフロー用。省略時は破棄 |
| `--no-pdf` | flag | `False` | PDF 生成をスキップ。`--keep-images <dir>` との併用が必須 |
| `-h, --help` | flag | - | ヘルプ表示 |

### デフォルト値の根拠

- `--quality 85`: Claude Vision の OCR 精度を維持しつつファイルサイズを抑えられる実用域。安全マージンとして 80 ではなく 85。
- `--delay 0.5`: 一般的なテキスト書籍のページめくりアニメーションが完了する時間。漫画など重い書籍では `--delay 1.0` 以上を推奨。
- `--stop-after 3`: 真っ白なページが 2 ページ連続するケースを許容しつつ、3 連続なら確実に末尾と判定。
- `--crop-top 60` / `--crop-bottom 40`: Kindle for Mac のツールバー高さ・進捗バー高さの経験値。書籍によって微調整が必要。

### 実行例

```bash
# 最も簡単
uv run kindle-screenshot

# 出力名指定
uv run kindle-screenshot -o "harry-potter-1.pdf"

# 漫画用（高画質 + 長め待機 + 厳しめ停止条件）
uv run kindle-screenshot -o "manga.pdf" --format png --delay 1.0 --stop-after 5
```

### 標準出力（例）

```
Kindle for Mac で対象書籍の 1 ページ目を開いてください。
準備ができたら Enter を押してください... [Enter]

Kindle ウィンドウを検出しました（window_id=12345, size=1024x1400）

3 秒後に開始します。Kindle ウィンドウが前面にあることを確認してください...
3... 2... 1... 開始

[  1] capturing... hash=a3f8...  ✓
[  2] capturing... hash=b7d2...  ✓
...
[247] capturing... hash=d4a1...  ✓ (重複 1/3)
[248] capturing... hash=d4a1...  ✓ (重複 2/3)
[249] capturing... hash=d4a1...  ✓ (重複 3/3) → 末尾判定。終了。

末尾の重複 3 ページを除外。247 ページを PDF 化中...
出力: ./kindle-20260505-143022.pdf (12.4 MB)
完了。
```

### 終了コード

| コード | 意味 |
|-------|------|
| 0 | 正常終了（PDF 出力済み） |
| 1 | ユーザー操作によるキャンセル（Enter 待ちで Ctrl+C 等） |
| 2 | Kindle.app が起動していない |
| 3 | macOS 権限不足 |
| 4 | キャプチャ失敗（リトライ後も失敗） |
| 130 | Ctrl+C 中断（ユーザーが PDF 化を辞退した場合） |

## 5. モジュール構成

### ディレクトリ構造

```
kindle-screenshot/
├── pyproject.toml          # uv プロジェクト定義 + 依存
├── README.md
├── .python-version         # uv 用 Python バージョン固定
├── .gitignore              # .venv/, *.pyc, dist/, *.pdf 等
├── src/
│   └── kindle_screenshot/
│       ├── __init__.py
│       ├── __main__.py     # python -m kindle_screenshot で実行
│       ├── cli.py          # argparse + メインフロー
│       ├── capture.py      # screencapture ラッパー
│       ├── input.py        # osascript ラッパー
│       ├── hashing.py      # 画像ハッシュ + 連続重複検出
│       └── pdf.py          # img2pdf ラッパー
└── tests/
    ├── __init__.py
    ├── test_hashing.py
    ├── test_pdf.py
    └── test_cli.py
```

### モジュール責務

#### `cli.py`

CLI 引数を argparse で定義し、全体フローをオーケストレーションする。

責務:
- 引数パースとバリデーション
- Kindle 起動確認 → ウィンドウ ID 取得 → ループ → PDF 化 の流れ制御
- 例外ハンドリング（KeyboardInterrupt、subprocess エラー等）
- 一時ディレクトリの作成・クリーンアップ

#### `capture.py`

画面キャプチャ関連。

主要関数:
- `get_kindle_window_bounds() -> tuple[int, int, int, int]`: osascript で Kindle.app のフロントウィンドウの `position` と `size` を取得し、`(x, y, width, height)` のタプルを返す。Kindle for Mac は AppleScript の `id` プロパティ非対応（issue #7）のため、ID ではなく矩形領域で扱う。想定外の osascript 出力（要素数 != 4 や非数値）は `KindleNotFoundError` に翻訳する。
- `capture_region_to_png(bounds: tuple[int, int, int, int], out: Path) -> None`: `screencapture -R x,y,w,h -t png -x <out>` で指定矩形領域を PNG キャプチャする。座標は論理ピクセル（ポイント）。負の y 座標（マルチディスプレイの上方向ディスプレイ）にも対応。
- `process_image(src_png: Path, dst: Path, fmt: str, quality: int, crop_top, crop_bottom, crop_left, crop_right) -> None`: PNG 中間ファイルを Pillow で読み、上下左右の余白を除去して目的形式（JPEG / PNG）で保存。中間 PNG は処理後に削除。

#### `input.py`

Kindle.app の制御とキー送信。

主要関数:
- `is_kindle_running() -> bool`: osascript で Kindle.app の起動状態を確認
- `activate_kindle() -> None`: Kindle.app を前面に出す（フォーカス奪取対策、毎ループ前に呼ぶ）
- `send_right_arrow() -> None`: System Events 経由で右矢印キーを送る

#### `hashing.py`

画像ハッシュ計算と連続重複検出。

主要関数 / クラス:
- `compute_hash(img: Path) -> str`: Pillow で画像を 64x64 グレースケールに縮小 → ピクセルバイト列の SHA256 を返す。完全に同一フレームの判定として十分な堅牢性。
- `class DuplicateDetector(stop_after: int)`:
  - `add(h: str) -> bool`: 内部で連続重複カウンタを更新し、`stop_after` 回連続で同じハッシュなら `True`（停止すべき）を返す
  - `recent_duplicates_count -> int`: 末尾何枚を除外すべきかを呼び出し側に伝える

#### `pdf.py`

PDF 生成。

主要関数:
- `images_to_pdf(images: list[Path], output: Path) -> None`: img2pdf で画像群を 1 つの PDF にまとめる。再エンコードなし。

## 6. エラーハンドリング

| エラーケース | 対処 |
|------------|------|
| Kindle.app が起動していない | 案内メッセージ表示、終了コード 2 |
| Screen Recording 権限不足 | System Settings の該当ページへの導線を表示、終了コード 3 |
| Accessibility 権限不足 | 同上、終了コード 3 |
| screencapture コマンド失敗 | 同一ページで 1 回リトライ、再失敗で中断扱い（取得済みページの PDF 化を提案） |
| キャプチャ画像が 0 byte | screencapture 失敗と同等扱い |
| `Ctrl+C` 中断 | 「ここまでで PDF 化しますか？ [Y/n]」プロンプト、Yes なら PDF 化、No なら破棄 |
| `--max-pages` 到達 | 警告出力後、取得済みページで PDF 化（停止条件未到達で終了） |
| Kindle ウィンドウが途中で消えた | 中断扱い、PDF 化を提案 |
| 想定外の osascript 出力（カンマ区切り 4 要素でない、非数値） | `KindleNotFoundError` に翻訳して終了コード 2 |
| ループ中にユーザーがウィンドウを移動・リサイズ | `screencapture -R` は固定領域なので以降のキャプチャがズレる。README で「実行中はウィンドウを動かさない」と注意喚起 |
| osascript `-1728` エラー（AppleScript 非対応） | 権限不足ではなく Kindle アプリのバージョン互換性問題の可能性を案内。エラー文に `(-1728)` が含まれていればそれを優先案内。終了コード 3。issue #7（`id of front window` 非対応）/ issue #9（`tell application "Kindle"` 非対応）の経緯を踏まえる |
| `--no-pdf` 単独指定（`--keep-images` なし） | argparse の `parser.error()` でエラー終了（exit 2）。エラーメッセージに「`--no-pdf` を指定する場合は `--keep-images <dir>` の指定が必要です」を含める（issue #14） |

## 7. テスト戦略

### ユニットテスト（pytest、CI 対応可能）

- `test_hashing.py`:
  - 同一画像でハッシュが一致する
  - 異なる画像でハッシュが異なる
  - `DuplicateDetector` が N 連続重複で True を返す
  - 重複が途切れたらカウンタがリセットされる
- `test_pdf.py`:
  - Pillow で生成した合成画像群から PDF を生成
  - 生成 PDF のページ数・各ページサイズが期待通り
- `test_cli.py`:
  - 各引数のパース
  - タイムスタンプベースのデフォルトファイル名生成
  - `--quality` の範囲外（0, 101 等）でエラー

### 手動統合テスト（README に手順を記載）

- 実際の Kindle for Mac で短い書籍を 1 冊取り込み → PDF を Claude Code に投げて読めることを確認
- 漫画 1 冊（固定レイアウト）で動作確認
- 途中 `Ctrl+C` 中断 → プロンプト → PDF 化のフロー確認
- macOS 権限がない状態で起動 → 適切な案内が出ることを確認

### 目標カバレッジ

ユニットテストで 80% 以上。subprocess を呼ぶラッパー関数（`capture.py` / `input.py`）はモックでカバー。

## 8. 既知の制約・リスク

1. **macOS / Kindle for Mac バージョン依存**: 現状はスクリーンショットが取れるが、将来のアップデートでコンテンツ保護フラグが導入されると突然黒画面化する可能性。README に動作確認済みバージョンを記載し、ユーザー側で事前検証する運用にする。
2. **ハッシュ誤検出**: 真っ白なページが連続する書籍で誤って末尾判定する可能性。`--stop-after` で調整可能、`--max-pages` で安全弁。
3. **フォーカス奪取**: ループ中に通知バナーや他アプリがフォーカスを取ると右矢印キーが Kindle に届かない。毎ループ前に `activate_kindle()` を呼ぶことで軽減するが、完全防御は macOS の制約上不可。README に「実行中は Mac を触らない」と明記。
4. **DRM 保護書籍**: 一部書籍は Kindle for Mac でも黒画面になる。ユーザーが事前に手動キャプチャで動作確認する前提。
5. **法的・倫理的事項**: 自身が購入した書籍を私的使用目的で複製する範囲に限定。配布は著作権法違反となる。README に明記。

## 9. 将来の拡張余地（本スコープ外）

- 名前付きプロファイルでの余白設定の保存（書籍ごとの crop 値再利用）
- 並列キャプチャ・PDF 化（画質と引き換えに高速化）
- Kindle Cloud Reader 対応の別実装（ブラウザ自動化）
- iPad の Kindle アプリを QuickTime ミラーリング経由でキャプチャするフロー
- OCR 後処理によるテキスト埋め込み PDF（検索可能化）

これらは v1 ではスコープ外とし、必要になった時点で別 spec として起こす。
