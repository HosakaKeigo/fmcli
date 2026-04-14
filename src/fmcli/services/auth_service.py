"""認証サービス."""

from __future__ import annotations

from fmcli.core.errors import AuthError, FmcliError
from fmcli.domain.envelopes import Envelope
from fmcli.domain.error_codes import AuthErrorType
from fmcli.domain.models import Profile
from fmcli.domain.types import AuthScope, StatusScope
from fmcli.infra.auth_store import delete_credential, load_credential, save_credential
from fmcli.infra.profile_store import (
    list_profiles,
    save_profile,
)
from fmcli.infra.session_cache import cache_token, clear_cached_token, resolve_cached_session
from fmcli.services.api_factory import create_api


def login(
    profile: Profile,
    username: str,
    password: str,
    *,
    scope: AuthScope = "database",
) -> Envelope:
    """ログインしてトークンをキャッシュし、profile を自動保存する."""
    api = create_api(profile)
    with api:
        try:
            token, api_info = api.login(username, password)
            cache_token(profile, token, scope=scope)
            credential_saved = save_credential(profile.profile_key, username, password)

            # profile を自動保存
            prof = profile.model_copy(update={"name": profile.profile_key, "username": username})
            save_profile(prof)

            messages: list[str] = []
            if not credential_saved:
                messages.append(
                    "警告: 認証情報を keyring に保存できませんでした。"
                    "セッション切れ時の自動リフレッシュは利用できません。"
                )

            return Envelope.from_profile(
                prof,
                command="auth login",
                data={
                    "message": "Login successful",
                    "auth_scope": scope,
                    "host": profile.canonical_host,
                    "database": profile.database,
                    "profile_key": prof.profile_key,
                    "credential_persisted": credential_saved,
                },
                api=api_info,
                messages=messages,
            )
        except FmcliError:
            raise
        except Exception as e:
            raise AuthError(
                f"Login failed: {e}",
                error_type=AuthErrorType.INVALID,
                host=profile.canonical_host,
                database=profile.database,
            ) from e


def logout(profile: Profile, *, scope: StatusScope = "auto") -> Envelope:
    """ログアウトしてキャッシュを削除する."""
    resolved = resolve_cached_session(profile, scope=scope)
    if not resolved:
        return Envelope.from_profile(
            profile,
            command="auth logout",
            data={
                "message": "No active session",
                "host": profile.canonical_host,
                "database": profile.database,
            },
        )
    token, resolved_scope = resolved

    api = create_api(profile)
    api.set_token(token)
    with api:
        try:
            api_info = api.logout()
            clear_cached_token(profile, scope=resolved_scope)
            delete_credential(profile.profile_key)
            return Envelope.from_profile(
                profile,
                command="auth logout",
                data={
                    "message": "Logout successful",
                    "auth_scope": resolved_scope,
                    "host": profile.canonical_host,
                    "database": profile.database,
                },
                api=api_info,
            )
        except Exception:
            clear_cached_token(profile, scope=resolved_scope)
            return Envelope.from_profile(
                profile,
                command="auth logout",
                data={
                    "message": "Session cleared (server logout may have failed)",
                    "auth_scope": resolved_scope,
                    "host": profile.canonical_host,
                    "database": profile.database,
                },
            )


def list_sessions() -> Envelope:
    """保存済みプロファイルとセッション状態の一覧を返す."""
    profiles = list_profiles()
    sessions: list[dict[str, object]] = []

    for prof in profiles:
        resolved = resolve_cached_session(prof, scope="auto")
        has_session = resolved is not None
        scope_val = resolved[1] if resolved else None
        has_credential = load_credential(prof.profile_key) is not None
        sessions.append(
            {
                "profile_key": prof.profile_key,
                "host": prof.canonical_host,
                "database": prof.database,
                "username": prof.username,
                "has_session": has_session,
                "auth_scope": scope_val,
                "credential_persisted": has_credential,
            }
        )

    return Envelope(
        ok=True,
        command="auth list",
        data=sessions,
    )


def status(profile: Profile, *, scope: StatusScope = "auto") -> Envelope:
    """認証状態を確認する."""
    has_credential = load_credential(profile.profile_key) is not None
    resolved = resolve_cached_session(profile, scope=scope)
    if not resolved:
        return Envelope.from_profile(
            profile,
            command="auth status",
            data={
                "authenticated": False,
                "message": "No cached session",
                "auth_scope": scope,
                "host": profile.canonical_host,
                "database": profile.database,
                "profile_key": profile.profile_key,
                "credential_persisted": has_credential,
            },
        )
    token, resolved_scope = resolved

    api = create_api(profile)
    api.set_token(token)
    with api:
        valid, api_info = api.validate_session()
        return Envelope.from_profile(
            profile,
            command="auth status",
            data={
                "authenticated": valid,
                "message": "Session valid" if valid else "Session expired",
                "auth_scope": resolved_scope,
                "host": profile.canonical_host,
                "database": profile.database,
                "profile_key": profile.profile_key,
                "credential_persisted": has_credential,
            },
            api=api_info,
        )
