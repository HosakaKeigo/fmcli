"""標準出力 envelope."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from fmcli.domain.models import Pagination

if TYPE_CHECKING:
    from fmcli.domain.models import Profile


class ApiInfo(BaseModel):
    """API 呼び出し情報."""

    method: str = ""
    url: str = ""
    duration_ms: float | None = None


class AvailableProfile(BaseModel):
    """エラー時に提示する利用可能プロファイル情報."""

    profile_key: str
    host: str
    database: str


class ErrorDetail(BaseModel):
    """正規化エラー詳細."""

    type: str | None = None
    message: str
    error_code: str | None = None
    http_status: int | None = None
    api_code: int | None = None
    retryable: bool = False
    hint: str = ""
    host: str = ""
    database: str = ""
    available_profiles: list[AvailableProfile] | None = None


class Envelope(BaseModel):
    """CLI 標準出力 envelope."""

    ok: bool = True
    command: str = ""
    profile: str = ""
    database: str = ""
    layout: str = ""
    data: Any = None
    pagination: Pagination | None = None
    api: ApiInfo | None = None
    messages: list[str] = Field(default_factory=list)
    script_results: dict[str, Any] | None = None
    error: ErrorDetail | None = None

    @classmethod
    def from_profile(cls, profile: Profile, *, command: str, **kwargs: Any) -> Envelope:
        """Profile からプロファイル情報を引き継いで Envelope を生成する."""
        return cls(
            profile=profile.profile_key,
            database=profile.database,
            command=command,
            **kwargs,
        )
