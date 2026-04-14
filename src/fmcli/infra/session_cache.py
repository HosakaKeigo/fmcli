"""セッションキャッシュ管理."""

from __future__ import annotations

import logging

from fmcli.domain.models import Profile
from fmcli.domain.types import AuthScope, StatusScope
from fmcli.infra.auth_store import delete_session, load_session, save_session

logger = logging.getLogger(__name__)


def get_cached_token(profile: Profile) -> str | None:
    """キャッシュ済みトークンを取得する."""
    resolved = resolve_cached_session(profile)
    if resolved is None:
        return None
    token, _ = resolved
    return token


def resolve_cached_session(
    profile: Profile,
    *,
    scope: StatusScope = "auto",
) -> tuple[str, AuthScope] | None:
    """キャッシュ済みトークンと採用 scope を取得する."""
    scopes: tuple[AuthScope, ...] = ("database", "host") if scope == "auto" else (scope,)

    for candidate in scopes:
        token = load_session(_session_key(profile, candidate))
        if token:
            logger.debug("session cache hit scope=%s", candidate)
            return token, candidate
    logger.debug("session cache miss")
    return None


def cache_token(profile: Profile, token: str, *, scope: AuthScope = "database") -> None:
    """トークンをキャッシュする."""
    save_session(_session_key(profile, scope), token)


def clear_cached_token(profile: Profile, *, scope: AuthScope) -> None:
    """キャッシュ済みトークンを削除する."""
    delete_session(_session_key(profile, scope))


def _session_key(profile: Profile, scope: AuthScope) -> str:
    host = profile.canonical_host
    if scope == "host":
        return host
    return f"{host}|{profile.database}"
