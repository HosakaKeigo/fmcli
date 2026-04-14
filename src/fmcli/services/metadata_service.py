"""メタデータ参照サービス."""

from __future__ import annotations

from typing import Any

from fmcli.core.errors import AuthError
from fmcli.domain.envelopes import ApiInfo, Envelope
from fmcli.domain.error_codes import AuthErrorType
from fmcli.domain.models import Profile
from fmcli.infra.filemaker_api import FileMakerAPI
from fmcli.services import session_helper
from fmcli.services.api_factory import create_api
from fmcli.services.session_helper import call_with_refresh


def host_info(profile: Profile) -> Envelope:
    """ホスト情報を取得する (認証不要)."""
    api = create_api(profile)
    with api:
        body, api_info = api.get_product_info()
    return Envelope.from_profile(
        profile,
        command="host info",
        data=body.get("response", {}).get("productInfo", {}),
        api=api_info,
    )


def database_list(
    profile: Profile,
    username: str | None = None,
    password: str | None = None,
) -> Envelope:
    """データベース一覧を取得する (Basic 認証).

    username/password が未指定の場合は keyring から取得する。
    """
    from fmcli.infra.auth_store import load_credential

    if not username or not password:
        cred = load_credential(profile.canonical_host)
        if cred:
            username, password = cred
        else:
            raise AuthError(
                "認証情報がありません。先に 'fmcli auth login' するか、"
                "--username を指定してください。",
                error_type=AuthErrorType.REQUIRED,
                host=profile.canonical_host,
                database="",
            )

    api = create_api(profile)
    with api:
        body, api_info = api.get_databases(username, password)

        return Envelope.from_profile(
            profile,
            command="database list",
            data=body.get("response", {}).get("databases", []),
            api=api_info,
        )


def layout_list(profile: Profile) -> Envelope:
    """レイアウト一覧を取得する."""

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.get_layouts()

    body, api_info = call_with_refresh(profile, _call)
    layouts = body.get("response", {}).get("layouts", [])

    return Envelope.from_profile(
        profile,
        command="layout list",
        data=layouts,
        api=api_info,
    )


def _fetch_layout_metadata(profile: Profile, layout: str) -> tuple[dict[str, Any], ApiInfo]:
    """レイアウトメタデータの共通取得ヘルパー."""

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.get_layout_metadata(layout)

    body, api_info = call_with_refresh(profile, _call)
    response = body.get("response", {})
    return response, api_info


def layout_describe(profile: Profile, layout: str) -> Envelope:
    """レイアウトメタデータを取得する."""
    response, api_info = _fetch_layout_metadata(profile, layout)
    return Envelope.from_profile(
        profile,
        command="layout describe",
        layout=layout,
        data={
            "fieldMetaData": response.get("fieldMetaData", []),
            "portalMetaData": response.get("portalMetaData", {}),
            "valueLists": response.get("valueLists", []),
        },
        api=api_info,
    )


def layout_value_lists(profile: Profile, layout: str) -> Envelope:
    """値リスト情報を取得する."""
    response, api_info = _fetch_layout_metadata(profile, layout)
    value_lists = response.get("valueLists", [])

    # Format each value list with summary
    formatted = []
    for vl in value_lists:
        entry = {
            "name": vl.get("name", ""),
            "type": vl.get("type", ""),
            "count": len(vl.get("values", [])),
            "values": vl.get("values", []),
        }
        formatted.append(entry)

    return Envelope.from_profile(
        profile,
        command="layout describe --value-lists",
        layout=layout,
        data=formatted,
        api=api_info,
    )


def script_list(profile: Profile) -> Envelope:
    """スクリプト一覧を取得する."""

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.get_scripts()

    body, api_info = call_with_refresh(profile, _call)
    return Envelope.from_profile(
        profile,
        command="script list",
        data=body.get("response", {}).get("scripts", []),
        api=api_info,
    )
