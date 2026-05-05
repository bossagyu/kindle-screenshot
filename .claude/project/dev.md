# dev - プロジェクト固有の追記事項

## チェックリスト

### 実装着手前

- [ ] 設計ドキュメントに「エラーケース → 対処」表が含まれている場合、表の各行をテストケースとして書き出す。RED → GREEN の TDD でも、設計のエラー仕様は **必ず実装前にテスト計画に組み込む** <!-- Added 2026-05-05 from #1/#2: PR #2 で HIGH 2 件（権限不足の終了コード 3、Kindle ウィンドウ消滅時の中断扱い）が抜けていた。設計 §6 のエラー仕様を実装前にテストへ組み込んでいれば DA レビュー前に検出できた -->
- [ ] **AppleScript / OSAScript / 外部 OS API を使う実装の前に、対象アプリ / API のスクリプタブル属性を実機で事前確認する**。例: `osascript -e 'tell application "<App>" to get version'` や `osascript -e 'tell process "<App>" to get properties of front window'` を手動実行して、想定どおりにレスポンスが返ることを確認してからコードを書く <!-- Added 2026-05-05 from #7/#9: issue #7 は `id of front window` 非対応、issue #9 は `tell application "Kindle"` 非対応。事前に osascript を 1 度叩いていれば実装前に検出できた -->

### subprocess を呼ぶ実装

- [ ] `subprocess.run(check=True)` を使う場合、その呼び出しから上位への伝播経路上で `subprocess.CalledProcessError` を必ず捕捉する。または専用例外（`KindleNotFoundError` のような）に翻訳する層をラッパー関数内に入れる <!-- Added 2026-05-05 from #1/#2: PR #2 の HIGH 2 件は CalledProcessError の未捕捉が共通原因 -->
- [ ] 各 subprocess 呼び出しに対して、**正常系だけでなく異常系（非ゼロ終了、想定外 stdout、stderr あり）のテスト** を必ず追加する。モックで `MagicMock(returncode=1, stderr="...")` 形式の戻り値を作り、エラーパスをカバー <!-- Added 2026-05-05 from #1/#2: 初回 PR では正常系テストのみで、エラーパスのテストが薄かった -->
- [ ] エラーメッセージは「何が起きたか」だけでなく「ユーザーが何をすればよいか」（例: System Settings → Privacy & Security → Screen Recording で Terminal を許可）を含める <!-- Added 2026-05-05 from #1/#2: 設計 §6 が要求する「案内表示」要件を満たすため -->
- [ ] **エラーメッセージは原因を決め打ちせず、複数の可能性が考えられる場合は併記する**。例: osascript 失敗を「Accessibility 権限不足」と決め打ちすると、AppleScript 非対応や互換性問題の場合にユーザーを誤誘導する。「権限不足の可能性、または対象アプリの AppleScript 非対応の可能性」のように緩める <!-- Added 2026-05-05 from #7/#9: issue #9 で `_print_subprocess_error_guidance` が osascript -1728 エラーを「権限不足」と決め打ちで案内し、ユーザーが System Settings を確認しても解決しないミスリードが発生した -->

### 外部 OS API に依存する実装の PR 作成時

- [ ] **PR 説明に「実機での手動統合テスト記録」を必ず含める**。実行コマンド、結果（成功/失敗）、確認した OS バージョン、外部アプリバージョンを明記する。ユニットテスト pass だけでマージしてはいけない <!-- Added 2026-05-05 from #7/#9: v0.1 がユニット 100% pass で実環境では起動直後に終了した。手動統合テスト未実施が直接の原因 -->
- [ ] **仕様のグレーゾーンに踏み込む実装（ロケール依存、OS 仕様依存、外部アプリ仕様依存）は、PR 本文で「踏んだ罠」「未検証のリスク」を明示的に列挙する**。後続レビュアーが盲点を補えるようにする <!-- Added 2026-05-05 from #7/#9: AppleScript の `as string` がロケール依存で区切り文字が変わる可能性、`set frontmost` のアクセシビリティ権限要件など、グレーゾーンが多かった -->

### `for...else` 構文を使う場合

- [ ] `else` 節で実行される処理（max-pages 到達時の末尾トリム等）も、`break` で抜けた場合の処理と **同じ後処理を漏らさず実行する**。ループ内とループ外（else 節）で同じ責務がある場合、共通関数に切り出すか両側で明示的に呼び出す <!-- Added 2026-05-05 from #1/#2: PR #2 の MEDIUM #1 で max-pages 到達時の末尾重複トリムが抜けていた -->

## パターン / 慣習

### subprocess ラッパー層の例外翻訳

`capture.py` / `input.py` のような subprocess ラッパーモジュールでは、生の `subprocess.CalledProcessError` を上位に漏らさず、ドメイン例外（`KindleNotFoundError` 等）または `RuntimeError` に翻訳する。ただし権限不足は別途識別したいため、cli 層で `CalledProcessError` を直接 catch して終了コード 3 を返すパスも併用する。 <!-- Added 2026-05-05 from #1/#2: PR #2 の最終実装で採用した分担方針。dev 層と cli 層の役割分担が明確 -->

### ヒューリスティック分岐の根拠コメント

「取得済みページが 0 か否か」のようなヒューリスティック分岐を入れる場合、**コードコメントで「なぜそう判断するのが妥当か」を明記する**。後続レビュアーが判断の妥当性を検証できるようにするため。 <!-- Added 2026-05-05 from #1/#2: HIGH #2 修正時の「0 件→権限不足扱い、1 件以上→ウィンドウ消滅扱い」分岐がコメントで根拠化されており、DA 再レビューで「設計判断は妥当」と評価された -->

### AppleScript 互換性パターン

`tell application "<App>"` 構文が動かないアプリでは、System Events 経由のアクセシビリティ API を使う:
- ウィンドウ位置/サイズ取得: `tell application "System Events" to tell process "<App>" to get position/size of front window`
- アクティブ化: `tell application "System Events" to set frontmost of process "<App>" to true`
- 起動状態確認: `tell application "System Events" to exists process "<App>"`

新規 AppleScript を書く前にまず System Events 経由のパターンを試す。`tell application "<App>"` は対応アプリでのみ使う。 <!-- Added 2026-05-05 from #7/#9: Kindle for Mac は `tell application "Kindle"` も `id of front window` も非対応で、System Events 経由のみ動作した。同じパターンが他の非スクリプタブルアプリでも適用可能 -->

### ロケール非依存の AppleScript 出力フォーマット

AppleScript で複数値を返す際、`as string` での連結はロケール依存（カンマ vs ピリオドの区切り問題）が起きる可能性がある。**明示的に区切り文字を埋め込む形式（`& "," &`）を使い、Python 側で `.split(",")` でパースする**。 <!-- Added 2026-05-05 from #7/#9: issue #7 修正時に bounds を `"x,y,w,h"` 形式で返す設計を採用。ロケール依存を回避できた -->

## 注意事項

### TDD でのコミット粒度

1 タスク 1 コミット（テスト追加 + 実装）の粒度を維持すると bisect しやすく、レビュー時の差分も把握しやすい。ただし **複数タスクで共通モジュールを修正する場合は、import 文の散在に注意**（テストファイル先頭に集約しないと PEP8 違反になる）。最終タスクで全体整理を入れるか、フォーマッタを CI で走らせる。 <!-- Added 2026-05-05 from #1/#2: PR #2 で test_capture.py / test_cli.py のモジュールレベル import が関数定義の途中に散在した -->

### subprocess モックの限界

`unittest.mock.patch("...subprocess.run")` で AppleScript / シェルコマンドの戻り値を差し替えても、**AppleScript / シェルコマンド自体の構文・互換性は検証できない**。モックは「Python 側のロジック」しか見ない。外部 OS API に依存する箇所は、必ず実機で 1 度動作確認する。 <!-- Added 2026-05-05 from #7/#9: ユニットテスト 44/44 pass + カバレッジ 89% で v0.1 をリリースしたが、AppleScript の構文非対応で実環境では動かなかった。モックの限界を認識する必要がある -->
