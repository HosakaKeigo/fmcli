# FileMaker CLI

FileMaker Data API ラッパー CLI。Python で実装。

## プロジェクト概要

- **目的**: FileMaker Data API を安全・明示的に参照できる CLI を提供する
- **設計思想**: layout 中心・JSON 正本・説明可能・AI/LLM フレンドリー
- **スコープ**: 認証、メタデータ参照、レコード取得、find 検索、レコード作成（安全機構付き）
- **仕様書**: `docs/specs/overview.md`

## 技術スタック

- Python 3.12+, uv
- CLI: typer
- HTTP: httpx
- Validation: pydantic
- Output: rich
- テスト: pytest
- リンター/フォーマッター: ruff
- 型チェック: mypy

## ディレクトリ構造

```
src/fmcli/
├── cli/          # Typer コマンド定義（auth, profile, metadata, record, explain）
├── core/         # エラー階層（FmcliError）、共通定義
├── domain/       # Pydantic モデル（Profile, Envelope, Pagination 等）
├── infra/        # 外部I/O（FileMaker API クライアント、プロファイル/認証ストア）
├── services/     # ビジネスロジック（auth_service, session_helper）
└── main.py       # CLI エントリポイント
tests/unit/       # pytest ユニットテスト
```

## 開発ワークフロー

### Issue → 実装 → レビュー → PR

1. **Issue 作成**: 完了条件（受け入れ基準）を明確に記述する
2. **実装・テスト**: テストを書き、実装する。テストが通ることを確認する
3. **レビュー**: subagent および codex でコードレビューを実施する
4. **PR 作成**: レビュー結果を反映し、PR を作成する

### コード品質

- **pre-commit フック**: ruff（lint + format）と pytest を実行する
- コミット前に `ruff check` / `ruff format --check` / `pytest` が通ることを確認する
- CI でも同じチェックを実施する
- 品質ゲート: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`

### E2E 確認

- 品質ゲート通過後、マージ前に実際の CLI コマンドを実行して動作確認する
- 特に CLI のオプション有無・エラーハンドリング等、ユニットテストだけでは検証しにくい挙動を確認する
- 例: `uv run fmcli auth status`, `uv run fmcli profile list` など変更対象のコマンドを実行

## fmcli コマンドリファレンス

**重要: 以下に記載されたコマンドとオプションのみ使用すること。存在しないサブコマンドやオプションを推測して使わないこと。**

### 初期設定

```bash
# 対話ウィザードで一括設定（推奨）
fmcli auth config

# 個別ログイン（--host と -d は必須）
fmcli auth login --host https://fm.example.com -d MyDB
```

### 典型的なワークフロー

```bash
# 1. フィールド名を確認（検索前に必ず実行）
fmcli schema find-schema -l 'レイアウト名'

# 2. レコード検索
fmcli record find -l 'レイアウト名' -q '{"フィールド名":"値"}'

# 3. 必要に応じてフィールド型・属性を確認
fmcli layout describe -l 'レイアウト名'
```

### コマンド一覧

| コマンド | 説明 | 主要オプション |
|---------|------|--------------|
| `config set` | グローバル設定の保存 | KEY, VALUE (必須) |
| `config get` | グローバル設定の取得 | KEY (必須) |
| `config list` | 全グローバル設定の表示 | なし |
| `config unset` | グローバル設定の削除 | KEY (必須) |
| `auth config` | 対話ウィザードで一括設定（初期設定に推奨） | なし |
| `auth login` | ログイン（`--host`, `-d` は必須） | `--host`, `-d`, `-u`, `--scope`, `--password-stdin` |
| `auth logout` | ログアウト | `--host`, `-d`, `--scope` |
| `auth status` | 認証状態確認 | `--host`, `-d`, `--scope` |
| `auth list` | セッション一覧 | なし |
| `profile list` | プロファイル一覧 | なし |
| `profile show` | プロファイル詳細 | `--host`, `-d` |
| `host info` | ホスト情報 | `--host`, `-d` |
| `database list` | DB一覧 | `--host`, `-u` |
| `layout list` | レイアウト一覧 | `--host`, `-d`, `--filter` |
| `layout describe` | フィールド構造 | `-l` (必須), `--host`, `-d`, `--value-lists` |
| `script list` | スクリプト一覧 | `--host`, `-d` |
| `record get` | 単一レコード取得 | RECORD_ID (必須), `-l` (必須), `--fields`, `--portal` |
| `record list` | レコード一覧 | `-l` (必須), `--limit`, `--offset`, `--sort`, `--fields`, `--portal`, `--dry-run` |
| `record find` | レコード検索 | `-l` (必須), `-q` または `-f` (必須), `--limit`, `--offset`, `--sort`, `--fields`, `--portal`, `--first`, `--count`, `--with-schema`, `--dry-run` |
| `record create` | レコード作成 | `-l` (必須), `--field-data` または `-f` (必須), `--yes`/`-y`, `--dry-run`, `--skip-field-check`, `--script`, `--allow-scripts` |
| `record update` | レコード更新 | RECORD_ID (必須), `-l` (必須), `--field-data` または `-f` (必須), `--mod-id` (必須), `--yes`/`-y`, `--dry-run`, `--no-backup`, `--skip-field-check` |
| `record upload` | コンテナアップロード | RECORD_ID (必須), `-l` (必須), `--field` (必須), `--file` (必須), `--yes`/`-y`, `--dry-run`, `--repetition`, `--if-mod-id`, `--skip-field-check` |
| `schema find-schema` | 検索可能フィールド一覧 | `-l` (必須), `--host`, `-d`, `--filter`, `--type` |
| `schema output` | レイアウト出力構造 | `-l` (必須), `--host`, `-d` |
| `explain find` | find クエリの説明 | `-l` (必須), `-q` または `-f` (必須) |

### 注意事項

- `--fields` (`record get`/`list`/`find`) はクライアント側フィルタ（API は全フィールド返却し、表示時��絞り込み）
- `record find` では `--query`(`-q`) または `--query-file`(`-f`) のいずれかが必須
- `record find --count` は件数のみ返す: `{"found_count": N}`
- `record find --with-schema` は検索結果にスキーマ情報を付加: `{"records": [...], "schema": {...}}`
- `record find` でレコードが 0 件の場合（FM API code 402）はエラーではなく空配列 `[]` を返す
- `--sort` は `asc`/`desc` エイリアスに対応: `--sort 'Name:asc'` = `--sort 'Name:ascend'`
- `record create` では `--field-data` または `--field-data-file`(`-f`) のいずれかが必須
- `record create` はデフォルトで確認プロンプトを表示。非対話環境では `--yes` が必須
- `record create` はフィールド名を事前検証する。スキップするには `--skip-field-check`
- `record update` は `--mod-id` が必須（楽観的ロック）。事前に `record get` で modId を取得すること
- `record update` は更新前に自動で get し、modId 検証と diff 表示を行う
- `record update` は更新成功時に undo 情報を自動保存する（`--no-backup` でスキップ可）
- `record upload` はコンテナフィールドにファイルをアップロードする（multipart/form-data）
- `record upload` はコンテナ型かどうか事前検証する。スキップするには `--skip-field-check`
- `record upload` の `--if-mod-id` はオプション（クライアント側 precondition）
- `record upload` の undo は v1 では非対応（バイナリバックアップの複雑性のため）
- `--query` は JSON オブジェクトまたは配列: `-q '{"Name":"田中"}'` または `-q '[{"Name":"田中"},{"Name":"鈴木"}]'`
- `config set` で設定可能なキー: `timeout`（API タイムアウト秒数、正の整数）
- timeout 優先順位: `--timeout`（CLI フラグ）> `config.json` > デフォルト 60 秒
- 全コマンド共通オプション: `--host`, `-d`（常に明示指定が必要）
- グローバルオプション: `--format json|table`, `--verbose`, `--install-completion`, `--show-completion`
- カラー無効化: `NO_COLOR=1` 環境変数（[no-color.org](https://no-color.org/) 準拠）

## プロファイル解決

`--host` + `-d` の明示指定が必須。暗黙的な解決（デフォルトプロファイル、環境変数フォールバック）はない。
LLM が安全に利用できるよう、どのDBへの操作か常にコマンドで自明にする設計。

### セッション自動リフレッシュ
- `call_with_refresh()` が API コールをラップし、401/952 エラー時に keyring 認証情報で自動再ログイン
- keyring にパスワードが保存されていれば、セッション切れを意識せず使える

## 設計上の注意点

- FileMaker Data API の layout 中心モデルをそのまま反映する
- `delete` コマンドは持たない。`record create` / `record update` / `record upload` のみ安全機構付きでサポート
- JSON を正本出力とし、`--dry-run` / `--explain` で説明可能性を担保する
- エラーは正規化して返す（HTTP ステータス、API コード、人間向けメッセージ、retry 可否）
- FileMaker の日付形式は `MM/DD/YYYY`（例: `03/10/2026`）
