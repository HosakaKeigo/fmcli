"""エラーコード enum 定義."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class HttpStatus(IntEnum):
    """FileMaker Data API が返す HTTP ステータスコード."""

    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    UNSUPPORTED_MEDIA_TYPE = 415
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503

    @property
    def label(self) -> str:
        """日本語ラベルを返す."""
        return _HTTP_LABELS.get(self, "")

    @property
    def retryable(self) -> bool:
        """リトライ可能なステータスか."""
        return self in (
            HttpStatus.TOO_MANY_REQUESTS,
            HttpStatus.SERVICE_UNAVAILABLE,
        )


_HTTP_LABELS: dict[HttpStatus, str] = {
    HttpStatus.BAD_REQUEST: "不正なリクエスト",
    HttpStatus.UNAUTHORIZED: "権限がありません",
    HttpStatus.FORBIDDEN: "禁止されています",
    HttpStatus.NOT_FOUND: "見つかりません",
    HttpStatus.METHOD_NOT_ALLOWED: "メソッドが使用できません",
    HttpStatus.UNSUPPORTED_MEDIA_TYPE: "サポートされていないメディアタイプ",
    HttpStatus.TOO_MANY_REQUESTS: "リクエスト過多",
    HttpStatus.INTERNAL_SERVER_ERROR: "FileMaker エラー",
    HttpStatus.BAD_GATEWAY: "Bad Gateway",
    HttpStatus.SERVICE_UNAVAILABLE: "サービス利用不可",
}


class FmApiCode(IntEnum):
    """FileMaker Data API エラーコード (主要なもの).

    NOTE: 952-959 は Data API 固有のセッション/ライセンス関連コード。
    FileMaker 汎用エラーコード表の同番号とは意味が異なる場合がある。
    ref: Claris FileMaker Data API Guide
    """

    RECORD_MISSING = 100
    RECORD_MISSING_ALT = 101  # FileMaker legacy code, same semantics as 100
    LAYOUT_MISSING = 105
    TABLE_MISSING = 106
    RELATED_TABLE_MISSING = 110
    RECORD_LOCKED = 301
    FIND_CRITERIA_EMPTY = 400
    FIELD_NOT_FOUND = 401
    NO_RECORDS_MATCH = 402
    SERVER_UNAVAILABLE = 802
    SESSION_EXPIRED = 952
    SESSION_INVALID = 953
    SESSION_LIMIT = 954
    DATA_API_LICENSE = 958
    FIELD_VALUE_INVALID = 509
    DATA_API_DISABLED = 959

    @property
    def hint(self) -> str:
        """ユーザー向けヒントメッセージを返す."""
        return _FM_CODE_HINTS.get(self, "")

    @property
    def retryable(self) -> bool:
        """リトライ可能なエラーか."""
        return self in (
            FmApiCode.RECORD_LOCKED,
            FmApiCode.SESSION_EXPIRED,
            FmApiCode.SESSION_LIMIT,
        )


_FM_CODE_HINTS: dict[FmApiCode, str] = {
    FmApiCode.RECORD_MISSING: "レコードが見つかりません。レコード ID を確認してください。",
    FmApiCode.RECORD_MISSING_ALT: "レコードが見つかりません。レコード ID を確認してください。",
    FmApiCode.LAYOUT_MISSING: "レイアウト名を確認してください: `fmcli layout list`",
    FmApiCode.TABLE_MISSING: "テーブルが見つかりません。レイアウト名を確認してください。",
    FmApiCode.RELATED_TABLE_MISSING: (
        "関連テーブルが見つかりません。ポータル名を確認してください: "
        "`fmcli layout describe -l <レイアウト名>`"
    ),
    FmApiCode.RECORD_LOCKED: (
        "レコードが他のユーザーに使用されています。しばらく待ってリトライしてください。"
    ),
    FmApiCode.FIND_CRITERIA_EMPTY: "検索条件の構文エラーです。クエリを確認してください。",
    FmApiCode.FIELD_NOT_FOUND: (
        "レイアウト名またはフィールド名が正しいか確認してください。\n"
        "フィールド一覧: `fmcli schema find-schema -l <レイアウト名>`"
    ),
    FmApiCode.NO_RECORDS_MATCH: (
        "検索条件に一致するレコードがありません。クエリを見直してください。"
    ),
    FmApiCode.FIELD_VALUE_INVALID: (
        "フィールド値が不正です。フィールドの型に合った値を指定してください。\n"
        "フィールド型の確認: `fmcli layout describe -l <レイアウト名>`"
    ),
    FmApiCode.SERVER_UNAVAILABLE: (
        "FileMaker Server に接続できません。サーバーの状態を確認してください。"
    ),
    FmApiCode.SESSION_EXPIRED: (
        "セッション切れです。keyring 認証情報があれば自動リフレッシュされます。"
    ),
    FmApiCode.SESSION_INVALID: ("セッションが無効です。再ログインしてください: `fmcli auth login`"),
    FmApiCode.SESSION_LIMIT: (
        "FileMaker Data API の同時接続上限に達しました。しばらく待ってリトライしてください。"
    ),
    FmApiCode.DATA_API_LICENSE: (
        "Data API ライセンスエラーです。FileMaker Server の設定を確認してください。"
    ),
    FmApiCode.DATA_API_DISABLED: (
        "FileMaker Data API が無効です。サーバー管理者に連絡してください。"
    ),
}


class AuthErrorType(StrEnum):
    """認証エラーの種別."""

    REQUIRED = "auth_required"
    EXPIRED = "auth_expired"
    INVALID = "auth_invalid"
    FORBIDDEN = "auth_forbidden"
