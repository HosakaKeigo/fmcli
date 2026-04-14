# Authentication Strategy Spec

## Purpose

`fmcli` の認証を、人間と AI の両方にとって扱いやすい形に統一する。

この仕様では次を満たす。

- `auth login` だけで接続定義と認証取得を完了できる
- profile 名はユーザーに入力させず、自動生成して一意に保つ
- セッショントークンは keychain に保存する
- 実行時は `database -> host` の順で認証を探索する
- 認証が見つからなければ、AI が解釈しやすい形で認証要求を返す

## Goals

- one-step login にする
- 同一 host 上の複数 database を自然に扱える
- AI が暗黙状態を誤解しにくい
- token を平文ファイルに保存しない
- profile 名の命名責任をユーザーに持たせない

## Non-Goals

- `default` auth scope は持たない
- host 一覧の自動 discovery はしない
- 複数 host を横断してログイン可能な host 一覧を API から取得しない

## Terminology

### Connection Context

実行対象を表す接続情報。

- `host`
- `database`
- `username`
- `verify_ssl`

### Profile

接続情報のローカル保存単位。

profile 名は内部的に自動生成する。

### Session Scope

セッショントークンの保存粒度。

- `database`
  - キーは `host + database`
- `host`
  - キーは `host`

## CLI Behavior

### auth login

`auth login` は接続情報を受け取り、認証し、接続情報を profile として保存する。

想定オプション:

- `--host`
- `--database`
- `--username`
- `--password`
- `--scope database|host`
- `--no-verify-ssl`

`--profile` は受け付けない。

#### Default behavior

- profile は常に自動生成して保存する
- 既存の同一接続先 profile があれば上書きする
- `--scope` 未指定時は `database`

#### Auto-generated profile identity

profile の一意性は少なくとも次の組み合わせで決める。

- `host`
- `database`

将来、同一 `host + database` に対して複数 `username` を区別したい場合は、
一意キーに `username` を加える。

#### Recommended internal rule

内部一意キー:

`profile_key = canonical(host) + "|" + database`

canonical 化の最低要件:

- scheme を保持する
- host の末尾 `/` を落とす
- database 名はそのまま保持する

### auth status

`auth status` は指定された接続文脈に対して、どの scope の token が採用されるかを返す。

返すべき情報:

- `authenticated`
- `auth_scope`
- `host`
- `database`
- `profile_key`

### auth logout

`auth logout` は指定された接続文脈に対して token を削除する。

`auto` 指定時は探索順に従って採用された scope を削除する。

## Profile Storage

profile はローカルファイルに保存してよい。

保存対象:

- `host`
- `database`
- `username`
- `verify_ssl`
- 内部 `profile_key`

保存してはいけないもの:

- password
- session token

## Session Storage

session token は keychain に保存する。

### database scope

保存キー:

`session:{host}|{database}`

### host scope

保存キー:

`session:{host}`

## Runtime Resolution

コマンド実行時の認証解決順は次の通り。

1. `database` scope の token を探す
2. なければ `host` scope の token を探す
3. なければ認証エラーを返す

`default` scope は探索しない。

## Authentication Error Contract

認証がない、または再認証が必要な場合、AI が判定しやすい構造化エラーを返す。

最低限含めるべき内容:

- `type`
- `message`
- `hint`
- `host`
- `database`

例:

```json
{
  "ok": false,
  "error": {
    "type": "auth_required",
    "message": "Authentication required",
    "hint": "Run fmcli auth login --host https://example.com --database MainDB",
    "host": "https://example.com",
    "database": "MainDB"
  }
}
```

### Error types

- `auth_required`
- `auth_expired`
- `auth_invalid`

## AI Interaction Model

AI は認証失敗時に次のように動くことを想定する。

1. 構造化エラーを受け取る
2. `type=auth_required` または `type=auth_expired` を判定する
3. ユーザーに `auth login` を促す
4. 再実行する

このため、認証不足を単なる曖昧な RuntimeError にしないことが望ましい。

## UX Rationale

### Why not manual profile naming

- 接続先ごとに profile 名を考えるのは負担
- 同一接続先に重複 profile が増えやすい
- AI は profile 名より `host` と `database` を扱う方が安定する

### Why no default auth scope

- 暗黙 fallback が強すぎる
- AI が「なぜその認証が使われたか」を説明しにくい
- 誤った database へのアクセスを招きやすい

### Why host fallback is allowed

- 同一 host 上の複数 database を実用的に扱える
- database 専用 token がある場合はそちらを優先できる

## Migration Notes

旧実装からの移行では次を行う。

- `profile` 名ベースの session key を廃止する
- `host|database` / `host` ベースの session key に移行する
- 既存ユーザーには再ログインを要求してよい

## Open Questions

- profile 一意キーに初期段階から `username` を含めるか
- auto-generated profile 名を人間可読にするか、内部キーだけに寄せるか
- `auth login` 後にその接続文脈を default target にするか
