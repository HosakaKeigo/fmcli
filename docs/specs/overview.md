以下、**言語非依存の要件定義書ドラフト v0.1** としてまとめます。
対象は **FileMaker Data API をラップする read-only CLI** です。`googleworkspace/cli` のように、**人間にも AI/LLM にも扱いやすい CLI** を目標にします。`gws` は「built for humans and AI agents」「structured JSON output」を前面に出しており、今回の方向性と相性がよいです。 ([GitHub][1])

---

# FileMaker Data API ラッパー CLI 要件定義書 v0.1

## 1. 文書の目的

本書は、FileMaker Data API を利用して hosted database 上の情報を安全かつ一貫して参照できる **read-only CLI** の要件を定義する。
本 CLI は、開発者・運用者・AI エージェントが共通のコマンド体系で利用できることを重視する。

本 CLI は FileMaker Data API のうち、少なくとも以下の公開機能群を対象とする。

* 認証とセッション開始
* ホスト/データベース/レイアウト等のメタデータ取得
* 単一レコード取得
* レコード一覧取得
* find 実行

これらは FileMaker Data API の公式ガイドに含まれる代表的な機能であり、メタデータ取得、レコード取得、find は現在の主要ユースケースとして整理されている。 ([Claris Help][2])

---

## 2. 背景

FileMaker Data API は REST API として提供され、ホスト情報、データベース名、レイアウト名、レイアウトメタデータ、レコード取得、find などにアクセスできる。利用には対象データベース側で `fmrest` 拡張権限が有効である必要がある。 ([Claris Help][3])

一方、FileMaker Data API は **layout 文脈** が強く、単純な「テーブル CRUD」モデルで抽象化すると誤解や誤操作が起きやすい。たとえばレイアウトメタデータ取得は layout 単位で fields / portals / value lists を返し、レコード範囲取得も database と layout を指定して行う。 ([Claris Help][4])

そのため本 CLI は、FileMaker の実態に合った **layout 中心の概念モデル** を採用し、LLM が誤推論しにくい明示的なコマンド体系を持つ必要がある。

---

## 3. スコープ

### 3.1 対象範囲

本 CLI の対象は次の通り。

* FileMaker Server または FileMaker Cloud 上で公開された FileMaker Data API への接続
* 認証
* セッション管理
* メタデータ参照
* レコード参照
* find による検索
* 構造化出力
* AI/LLM が利用しやすい help / explain / dry-run / schema 表現

### 3.2 非対象範囲

初版では次を対象外とする。

* レコードの削除
* グローバルフィールド更新
* スクリプト実行
* コンテナアップロード
* サーバーファイルシステム操作
* GUI
* 自然言語のみでの曖昧操作
* 自動補完に依存した危険な推測実行

FileMaker Data API 自体は delete や script 実行も持つが、本 CLI は削除操作を対象外とする。レコード作成 (`record create`) とレコード更新 (`record update`) は安全機構付きでサポートする。 ([Claris Help][5])

---

## 4. 目標

本 CLI の目標は次の 5 点である。

### 4.1 安全性

書き込み操作は確認プロンプト・`--dry-run`・`--yes` フラグによる安全機構を備え、誤操作リスクを抑える。

### 4.2 明示性

database、layout、record、query などの主語をコマンド上で明示し、曖昧な自動推論を避ける。

### 4.3 機械可読性

JSON を正本として出力し、LLM・スクリプト・他ツールから再利用しやすくする。`gws` も structured JSON output を中核価値としている。 ([GitHub][1])

### 4.4 説明可能性

`--dry-run`、`--explain`、`schema` 的な補助コマンドにより、CLI がどの API をどう叩くかを説明可能にする。

### 4.5 FileMaker との整合

FileMaker Data API の layout 中心の構造をそのまま CLI の概念モデルに反映する。レイアウト名一覧取得、レイアウトメタデータ取得、レコード範囲取得はいずれも layout 指定を基準とする。 ([Claris Help][6])

---

## 5. 想定利用者

### 5.1 人間の利用者

* FileMaker 管理者
* API 利用開発者
* 運用担当
* 調査担当

### 5.2 AI/LLM 利用者

* コード生成エージェント
* オペレーション支援エージェント
* データ参照補助エージェント

AI/LLM 利用者に対しては、コマンド面の安定性、JSON 出力、明確なエラー構造、help の自己記述性が特に重要である。

---

## 6. 利用シナリオ

本 CLI は少なくとも次のシナリオを満たす必要がある。

1. 接続先ホストと database を登録し、ログインする。
2. 利用可能な database 一覧を確認する。
3. 特定 database の layout 一覧を確認する。
4. 特定 layout の fields / portals / value lists を確認する。
5. 特定 record ID のレコードを取得する。
6. 特定 layout のレコードを範囲指定で一覧取得する。
7. find 条件を指定して検索する。
8. 実行前に HTTP リクエスト内容を dry-run で確認する。
9. AI が `--json` の結果を受け取り、次のコマンドを組み立てる。

---

## 7. 概念モデル

本 CLI は以下の概念を中核とする。

### 7.1 Host

FileMaker Server / FileMaker Cloud の接続先。

### 7.2 Profile

接続設定の名前付き保存単位。host、database 既定値、認証方式、出力設定などを保持する。

### 7.3 Session

認証によって発行された一時トークン。接続設定とは分離して扱う。FileMaker Data API は login/logout のセッションモデルを持つ。 ([Claris Help][5])

### 7.4 Database

host 上の対象データベース。

### 7.5 Layout

レコード取得・検索・メタデータ参照の主要コンテキスト。レイアウトメタデータは field、portal、value list を layout 単位で返す。 ([Claris Help][4])

### 7.6 Record

layout 文脈で参照されるレコード。

### 7.7 Query

find 用の条件定義。簡易指定と生 JSON 指定の両方を許可する。

---

## 8. 機能要件

## 8.1 認証機能

CLI は `auth login` を起点に認証できなければならない。
認証方式は、少なくとも FileMaker Data API ガイドに沿った通常ログイン方式を扱える必要がある。ガイドには通常ログインに加え OAuth や FileMaker Cloud 向けヘッダも記載されているため、将来拡張を考慮した抽象化を持つことが望ましい。 ([Claris Help][5])

必須要件:

* 対話型ログイン
* 非対話型ログイン
* ログアウト
* 現在の認証状態確認
* セッション再利用
* セッション失効時の再ログイン誘導
* 秘密情報の安全な保存または非保存運用

期待コマンド例:

* `auth login`
* `auth logout`
* `auth status`

### 8.1.1 認証情報の保持

* 接続設定とセッショントークンは分離すること
* 短命トークンはキャッシュ的に扱うこと
* パスワードやトークンを標準出力やログに平文で出さないこと

## 8.2 プロファイル管理

CLI は複数接続先を扱える必要がある。

必須要件:

* profile 作成
* profile 一覧
* profile の既定切替
* profile の詳細表示
* profile ごとの host / database 既定値

## 8.3 メタデータ参照

FileMaker Data API の metadata 系機能に対応すること。Data API ではホスト製品情報、database 名、layout 名、script 名、layout metadata が取得できる。 ([Claris Help][2])

必須要件:

* host 情報取得
* database 一覧取得
* layout 一覧取得
* script 一覧取得
* layout metadata 取得

期待コマンド例:

* `host info`
* `database list`
* `layout list`
* `layout describe`
* `script list`

## 8.4 レコード取得

Data API の単一レコード取得および範囲取得に対応すること。範囲取得は offset、limit、sort、portal 関連指定を扱えることが望ましい。 ([Claris Help][7])

必須要件:

* record ID 指定での単一取得
* offset / limit による一覧取得
* sort 指定
* portal 関連結果の扱い
* 出力件数やページ情報の付与

期待コマンド例:

* `record get`
* `record list`

## 8.5 find 検索

Data API の find 実行に対応すること。
find は JSON ベースで表現可能であり、CLI では次の二層を持つことが望ましい。

* そのまま JSON を渡す正式ルート
* 単純条件向けの簡易指定ルート

必須要件:

* `--query` で生 JSON を受け付ける
* 複数条件の指定
* sort, limit, offset の指定
* explain 出力
* dry-run 出力

期待コマンド例:

* `record find`
* `explain find`

## 8.6 スキーマ補助

AI/LLM の成功率向上のため、layout metadata を使った補助機能を持つことが望ましい。

推奨要件:

* find に使える field 候補の説明
* 出力される fieldData / portalData の概形表示
* value list 名の確認
* layout の可視項目確認

期待コマンド例:

* `schema find`
* `schema output`

---

## 9. コマンド設計要件

### 9.1 コマンド面は静的であること

`gws` は Discovery Document から動的にコマンド面を組み立てる設計だが、FileMaker では API 面の広さより layout 文脈の重要性が高いため、本 CLI の公開コマンド面は静的で安定している方がよい。 `gws` の動的生成という思想は参考になるが、そのまま適用しない。 ([GitHub][8])

### 9.2 主語が明確であること

コマンドは `auth`、`profile`、`host`、`database`、`layout`、`script`、`record`、`schema` など、対象オブジェクトを先頭に置く。

### 9.3 write 系語彙を含まないこと

初版では `create` `update` `delete` などの write 系サブコマンドを持たない。

### 9.4 help が自己記述的であること

* 例示を含む
* JSON 出力例を含む
* 必須引数を明確に示す
* profile, database, layout の関係を説明する

---

## 10. 入出力要件

## 10.1 出力形式

CLI は少なくとも以下の出力形式を持つこと。

* JSON
* 表形式
* 生レスポンス
* 可能であれば NDJSON

### 10.1.1 正本出力

正本は JSON とする。
AI/LLM や他ツールが安定して利用できるよう、表形式は閲覧用補助と位置づける。`gws` も structured JSON output を重視している。 ([GitHub][1])

### 10.1.2 標準 envelope

CLI 独自の標準 envelope を持つことが望ましい。
最低限、以下を含む。

* `ok`
* `command`
* `profile`
* `database`
* `layout`
* `data`
* `pagination`
* `api`
* `messages`
* `error`

## 10.2 入力形式

CLI は次の入力手段を受け付けること。

* フラグ/オプション
* 標準入力
* JSON ファイル参照
* 環境変数

### 10.2.1 複雑条件の入力

find 条件は `@file.json` のようなファイル参照をサポートすることが望ましい。

---

## 11. AI/LLM フレンドリー要件

本 CLI は AI 利用を前提とするため、次を必須または推奨とする。

### 11.1 JSON 出力の安定性

バージョン間でキー構造が不必要に変わらないこと。

### 11.2 エラーの正規化

FileMaker のレスポンスメッセージをそのまま返すだけでなく、CLI 側で少なくとも以下へ正規化すること。

* HTTP ステータス
* API メッセージコード
* 人間向けメッセージ
* retry 可否
* 再試行方法のヒント

### 11.3 dry-run

実行される HTTP method、URL、主要ヘッダ、送信 body を確認できること。

### 11.4 explain

簡易条件がどのように Data API リクエストへ変換されるかを説明できること。

### 11.5 自動推測の抑制

database や layout を危険に推測して実行しないこと。候補提示までは可だが、実行は明示指定を原則とする。

### 11.6 構造把握支援

layout describe を中心に、後続の find や record list が組み立てやすい情報を返すこと。

---

## 12. 非機能要件

## 12.1 セキュリティ

* 秘密情報を標準出力に出さない
* ログ出力時は秘匿値をマスクする
* 設定保存時は OS 標準の安全な保管手段または同等の保護を使う
* TLS 検証の無効化は明示的な危険モードに限定する
* `fmrest` 権限が必要であることをドキュメントに明記する。Data API 利用には対象 privilege set で `fmrest` が必要である。 ([Claris Help][5])

## 12.2 可観測性

* `--verbose`
* `--trace`
* request ID 相当の表示
* 実行時間の計測
* リトライ記録

## 12.3 可搬性

* 主要 OS で動作すること
* 標準入出力中心で CI/CD やスクリプトに組み込みやすいこと

## 12.4 性能

* 通常の metadata / record get / small list に対して体感的に即応であること
* ページング処理ではメモリを浪費しないこと
* `--page-all` 相当がある場合は逐次処理を考慮すること

## 12.5 後方互換性

* コマンド名、主要オプション、JSON キーは慎重に変更する
* 破壊的変更時は明確なバージョニング方針を持つ

---

## 13. エラー要件

CLI は以下の失敗ケースを区別して扱う必要がある。

* 接続失敗
* TLS/証明書失敗
* 認証失敗
* 権限不足
* database 不存在
* layout 不存在
* record 不存在
* query 不正
* セッション失効
* タイムアウト
* レート制限または一時的障害

各エラーは、人間向けメッセージと機械可読なエラーコードの両方を返すこと。

---

## 14. 設定要件

CLI は次の設定を扱えること。

* 既定 profile
* 既定 host
* 既定 database
* 既定出力形式
* タイムアウト
* TLS 設定
* ログレベル

設定の優先順位は原則として次とする。

1. コマンド引数
2. 環境変数
3. profile 設定
4. システム既定値

---

## 15. 想定コマンド体系

これは要件を満たす一例であり、実装言語には依存しない。

```text
auth login
auth logout
auth status

profile add
profile list
profile use
profile show

host info
database list
layout list
layout describe
script list

record get
record list
record find

schema find
schema output
explain find
```

この体系は、FileMaker Data API の metadata / records / find の機能区分と整合し、かつ AI が主語を誤読しにくい構成を意図している。metadata と records の主要操作は Data API ガイド上でも個別に整理されている。 ([Claris Help][2])

---

## 16. 受け入れ基準

初版リリース時、少なくとも以下を満たせば受け入れ可能とする。

### 16.1 認証

* 対話型 `auth login` が成功する
* `auth status` で状態確認できる
* `auth logout` でセッション破棄できる

### 16.2 メタデータ

* `database list` で database 一覧取得
* `layout list` で layout 一覧取得
* `layout describe` で field / portal / value list 情報取得

### 16.3 レコード

* `record get` で単一レコード取得
* `record list` で limit/offset 指定取得
* `record find` で query JSON 指定検索

### 16.4 AI 利用性

* `--json` が安定した構造を返す
* `--dry-run` が利用できる
* エラーが正規化されている
* help に最小例が含まれる

---

## 17. 既知の設計方針

### 17.1 layout 中心

FileMaker Data API は layout を中心にメタデータや record range を扱うため、本 CLI も同じ中心軸を採用する。 ([Claris Help][4])

### 17.2 JSON 正本

AI/LLM を重視するため、JSON を第一級出力とする。これは `gws` の設計思想とも一致する。 ([GitHub][1])

### 17.3 動的コマンド生成は採用しない

`gws` の動的生成は広い API 群には有効だが、今回の対象は FileMaker Data API の狭く意味的に強い領域であるため、静的コマンドの方が適している。 ([GitHub][8])

### 17.4 高水準 DSL と raw JSON の併存

find 条件は単純ケース向けの簡易指定と、完全表現のための raw JSON 指定の両方を持つ。

---

## 18. 今後の拡張余地

将来バージョンでは次を検討可能とする。

* write 系操作
* script 実行
* interactive shell
* 補完強化
* レスポンス整形テンプレート
* AI エージェント向け専用サブコマンド
* OpenAPI 風 schema export

ただし初版では read-only を厳守する。

---

## 19. 未決事項

現時点の未決事項は以下。

* profile の保存形式
* セッション保存ポリシー
* 出力 envelope の最終 schema
* table 出力の詳細仕様
* find 簡易 DSL の文法範囲
* portal 出力の正規化方針
* 標準の exit code 一覧
* 対象とする最低 FileMaker Data API バージョン

---

## 20. 要約

本 CLI は、FileMaker Data API の read-only 機能を対象に、**layout 中心・JSON 正本・説明可能・AI 利用しやすい** ことを主要価値とする。
FileMaker Data API の公式機能区分である metadata、records、find を素直に反映しつつ、`gws` が重視する structured JSON と AI フレンドリーな CLI 体験を取り入れる。 ([Claris Help][2])

[1]: https://github.com/googleworkspace/cli/blob/main/README.md?utm_source=chatgpt.com "cli/README.md at main · googleworkspace/cli"
[2]: https://help.claris.com/en/data-api-guide/content/get-metadata.html?utm_source=chatgpt.com "Get metadata | Claris FileMaker Data API Guide"
[3]: https://help.claris.com/en/data-api-guide/content/design-app.html?utm_source=chatgpt.com "Design the FileMaker Data API solution - Claris Help Center"
[4]: https://help.claris.com/en/data-api-guide/content/get-layout-metadata.html?utm_source=chatgpt.com "Get layout metadata | Claris FileMaker Data API Guide"
[5]: https://help.claris.com/archive/docs/18/en/dataapi/?utm_source=chatgpt.com "FileMaker 18 Data API Guide - Claris Help Center"
[6]: https://help.claris.com/en/data-api-guide/content/get-layout-names.html?utm_source=chatgpt.com "Get layout names | Claris FileMaker Data API Guide"
[7]: https://help.claris.com/en/data-api-guide/content/get-range-of-records.html?utm_source=chatgpt.com "Get a range of records | Claris FileMaker Data API Guide"
[8]: https://github.com/googleworkspace/cli/blob/main/AGENTS.md?utm_source=chatgpt.com "AGENTS.md - googleworkspace/cli"
