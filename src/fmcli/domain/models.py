"""ドメインモデル."""

from __future__ import annotations

from pydantic import BaseModel


class Profile(BaseModel):
    """接続プロファイル."""

    name: str = ""
    host: str
    database: str = ""
    username: str = ""
    verify_ssl: bool = True

    @property
    def profile_key(self) -> str:
        """内部一意キー (canonical host | database)."""
        return make_profile_key(self.host, self.database)

    @property
    def canonical_host(self) -> str:
        """scheme を保持し末尾 / を除去した host."""
        return self.host.rstrip("/")


def make_profile_key(host: str, database: str) -> str:
    """host と database から内部一意キーを生成する."""
    canonical = host.rstrip("/")
    if database:
        return f"{canonical}|{database}"
    return canonical


def validate_host_scheme(host: str, *, allow_insecure_http: bool = False) -> str | None:
    """ホスト URL のスキームを検証する.

    デフォルトでは https:// のみ許可する。
    http:// を使用するには allow_insecure_http=True が必要。

    Returns:
        警告メッセージ（http:// opt-in 時）または None（問題なし時）。
    """
    from fmcli.core.errors import ConfigError

    normalized = host.strip().lower()
    if normalized.startswith("https://"):
        return None
    if normalized.startswith("http://"):
        if not allow_insecure_http:
            raise ConfigError(
                "安全でない HTTP 接続はデフォルトで拒否されます。\n"
                "http:// を使用するには --allow-insecure-http を指定してください。"
            )
        return (
            "WARNING: 安全でない HTTP 接続を使用しています。\n"
            "通信内容が暗号化されないため、認証情報が漏洩するリスクがあります。\n"
            "本番環境では https:// を使用してください。"
        )
    raise ConfigError(
        f"無効なホスト URL です: {host}\nhttps:// で始まるホスト URL を指定してください。"
    )


class Pagination(BaseModel):
    """ページネーション情報."""

    offset: int = 1
    limit: int = 100
    total_count: int = 0
    found_count: int = 0
    returned_count: int = 0
