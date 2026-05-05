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
- **AppleScript 互換性**: Kindle for Mac は `tell application "Kindle"` 構文をサポートせず（issue #9）、ウィンドウの `id` プロパティも露出していない（issue #7）。本ツールは System Events 経由のアクセシビリティ API（`process "Kindle"` のウィンドウ位置・サイズ取得、`set frontmost of process "Kindle" to true` によるアクティブ化）と `screencapture -R` を組み合わせて動作する。Kindle のメジャーアップデートで AppleScript の互換性が変わると突然動かなくなる可能性がある。実行時に osascript の `-1728` エラーが出た場合は、権限不足ではなく Kindle のバージョン互換性問題を疑うこと。
- **フォーカス奪取**: 実行中に通知バナーや他アプリにフォーカスを取られると、右矢印キーが Kindle に届かず同じページが連続キャプチャされて誤って終了判定される。実行中は Mac を触らない。
- **キャプチャ中はウィンドウを動かさないこと**: ツールはループ開始前に取得した Kindle ウィンドウの位置とサイズを使って `screencapture -R` で固定領域をキャプチャする。実行中にウィンドウを移動・リサイズすると、以降のページが途中で切れたり、別領域が写り込んだりする。また、Kindle ウィンドウは画面内に完全に表示しておくこと（オフスクリーンに押し出すと正しくキャプチャできない）。
- **ハッシュ誤検出**: 真っ白なページが連続する書籍では誤って末尾判定する可能性。`--stop-after 5` などで調整。
- **DRM 黒画面書籍**: Kindle for Mac でも特定書籍は画面キャプチャが黒くなる場合あり。本ツールでは対処不可。

## ライセンスと利用制限

このツールは **自身が購入した書籍を私的使用目的で複製する** 範囲でのみ使うこと（日本国著作権法 第 30 条）。生成された PDF を配布・共有することは著作権侵害にあたる可能性がある。商用利用・配布・複数人での共有はしないこと。
