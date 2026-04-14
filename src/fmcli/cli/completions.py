"""CLI オプションの動的シェル補完コールバック."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from fmcli.core.config import DEFAULT_CACHE_DIR
from fmcli.domain.models import Profile


def _list_profiles_safe() -> list[Profile]:
    """プロファイル一覧を安全に取得する (補完中のエラーは無視)."""
    with contextlib.suppress(Exception):
        from fmcli.infra.profile_store import list_profiles

        return list_profiles()
    return []


def complete_host(incomplete: str) -> list[str]:
    """--host の補完候補を返す."""
    hosts: set[str] = set()
    for prof in _list_profiles_safe():
        hosts.add(prof.canonical_host)
    return [h for h in sorted(hosts) if h.startswith(incomplete)]


def complete_database(incomplete: str) -> list[str]:
    """--database の補完候補を返す."""
    databases: set[str] = set()
    for prof in _list_profiles_safe():
        if prof.database:
            databases.add(prof.database)
    return [d for d in sorted(databases) if d.startswith(incomplete)]


def _resolve_active_profile_key(
    host: str | None = None,
    database: str | None = None,
    allow_insecure_http: bool = False,
) -> str | None:
    """現在のアクティブプロファイルキーを安全に取得する (補完中のエラーは無視).

    host / database が指定されている場合はそれを使って解決する。
    """
    with contextlib.suppress(Exception):
        from fmcli.infra.profile_store import resolve_profile

        prof = resolve_profile(
            host=host, database=database, allow_insecure_http=allow_insecure_http
        )
        return prof.profile_key
    return None


def _extract_context_params() -> tuple[str | None, str | None, bool]:
    """Click コンテキストから --host / --database / --allow-insecure-http の値を取得する."""
    import click

    with contextlib.suppress(Exception):
        ctx = click.get_current_context(silent=True)
        if ctx is not None:
            host = ctx.params.get("host")
            database = ctx.params.get("database")
            allow_insecure_http = bool(ctx.params.get("allow_insecure_http"))
            return host or None, database or None, allow_insecure_http
    return None, None, False


def complete_layout(incomplete: str) -> list[str]:
    """--layout の補完候補をキャッシュから返す.

    補完コンテキストから --host / --database / --allow-insecure-http を取得し、
    アクティブプロファイルが解決できる場合はそのプロファイルのレイアウトのみ返す。
    解決できない場合は全プロファイルのレイアウトにフォールバックする。
    """
    host, database, allow_insecure_http = _extract_context_params()
    profile_key = _resolve_active_profile_key(
        host=host, database=database, allow_insecure_http=allow_insecure_http
    )
    if profile_key is not None:
        layouts = load_layout_cache_for_profile(profile_key)
    else:
        layouts = load_layout_cache()
    return [name for name in layouts if name.startswith(incomplete)]


# --- レイアウトキャッシュ ---


def _layout_cache_path() -> Path:
    return DEFAULT_CACHE_DIR / "layouts.json"


def save_layout_cache(profile_key: str, layout_names: list[str]) -> None:
    """レイアウト名をキャッシュに保存する."""
    with contextlib.suppress(Exception):
        cache_path = _layout_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        cache: dict[str, list[str]] = {}
        if cache_path.exists():
            with contextlib.suppress(json.JSONDecodeError):
                from fmcli.core.compat import read_text_utf8

                cache = json.loads(read_text_utf8(cache_path))

        cache[profile_key] = sorted(set(layout_names))
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def load_layout_cache() -> list[str]:
    """キャッシュから全プロファイルのレイアウト名を返す (重複排除・ソート済み)."""
    with contextlib.suppress(Exception):
        cache_path = _layout_cache_path()
        if cache_path.exists():
            from fmcli.core.compat import read_text_utf8

            data = json.loads(read_text_utf8(cache_path))
            names: set[str] = set()
            for layouts in data.values():
                names.update(layouts)
            return sorted(names)
    return []


def load_layout_cache_for_profile(profile_key: str) -> list[str]:
    """指定プロファイルのレイアウト名をキャッシュから返す (ソート済み)."""
    with contextlib.suppress(Exception):
        cache_path = _layout_cache_path()
        if cache_path.exists():
            from fmcli.core.compat import read_text_utf8

            data = json.loads(read_text_utf8(cache_path))
            layouts = data.get(profile_key, [])
            return sorted(layouts) if isinstance(layouts, list) else []
    return []
