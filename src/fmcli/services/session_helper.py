"""セッション取得・自動リフレッシュヘルパー."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from rich.console import Console

from fmcli.core.errors import ApiError, AuthError, FmcliError
from fmcli.domain.envelopes import ApiInfo
from fmcli.domain.error_codes import AuthErrorType, FmApiCode
from fmcli.domain.models import Profile
from fmcli.domain.types import AuthScope
from fmcli.infra.auth_store import load_credential
from fmcli.infra.filemaker_api import FileMakerAPI
from fmcli.infra.session_cache import cache_token, resolve_cached_session
from fmcli.services.api_factory import create_api

logger = logging.getLogger(__name__)

_console = Console(stderr=True)

ApiResult = tuple[dict[str, Any], ApiInfo]


def _get_api(profile: Profile) -> tuple[FileMakerAPI, AuthScope]:
    """認証済み API クライアントと scope を返す（内部用）.

    セッショントークンがない場合、keyring の認証情報で自動ログインを試みる。
    呼び出し元が close() を保証すること。
    """
    resolved = resolve_cached_session(profile)

    scope: AuthScope
    if resolved is not None:
        token, scope = resolved
    else:
        scope = "database"
        token = _auto_login(profile, scope=scope)

    api = create_api(profile)
    api.set_token(token)
    return api, scope


def _call_fn(fn: Callable[[FileMakerAPI], ApiResult], api: FileMakerAPI) -> ApiResult:
    """verbose 時はスピナー付きで API を呼び出す."""
    from fmcli.core.output import is_verbose

    if is_verbose():
        with _console.status("データを取得中...", spinner="dots"):
            return fn(api)
    return fn(api)


def call_with_refresh(
    profile: Profile,
    fn: Callable[[FileMakerAPI], ApiResult],
) -> ApiResult:
    """API 呼び出しを実行し、セッション切れなら自動リフレッシュしてリトライする."""
    api, scope = _get_api(profile)
    try:
        return _call_fn(fn, api)
    except (ApiError, AuthError) as e:
        # http_client が 401 → AuthError(EXPIRED) に変換するため、
        # AuthError は retryable フラグで判定。ApiError は SESSION_EXPIRED のみ。
        is_session_expired = (isinstance(e, AuthError) and e.retryable) or (
            isinstance(e, ApiError) and e.api_code == FmApiCode.SESSION_EXPIRED
        )
        if is_session_expired:
            logger.debug("Session expired, attempting auto-refresh")
            api.close()
            token = _auto_login(profile, scope=scope)
            api = create_api(profile)
            api.set_token(token)
            try:
                return _call_fn(fn, api)
            except Exception:
                api.close()
                raise
        raise
    finally:
        api.close()


def _auto_login(profile: Profile, *, scope: AuthScope = "database") -> str:
    """keyring の認証情報で自動ログインする."""
    cred = load_credential(profile.profile_key)
    if not cred:
        raise AuthError(
            "セッション切れです。認証情報がないため自動リフレッシュできません。"
            "'fmcli auth login' で再認証してください。",
            error_type=AuthErrorType.REQUIRED,
            host=profile.canonical_host,
            database=profile.database,
        )

    username, password = cred
    logger.debug("Auto-login for %s (scope=%s)", profile.canonical_host, scope)

    api = create_api(profile)
    with api:
        try:
            token, _ = api.login(username, password)
            cache_token(profile, token, scope=scope)
            return token
        except FmcliError:
            raise
        except Exception as e:
            raise AuthError(
                f"自動リフレッシュに失敗しました: {e}",
                error_type=AuthErrorType.INVALID,
                host=profile.canonical_host,
                database=profile.database,
            ) from e
