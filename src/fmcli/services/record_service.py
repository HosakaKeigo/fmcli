"""レコード取得サービス."""

from __future__ import annotations

import logging
import os
from typing import Any, NamedTuple

from fmcli.core.errors import ApiError
from fmcli.domain.envelopes import Envelope
from fmcli.domain.error_codes import FmApiCode
from fmcli.domain.models import Pagination, Profile
from fmcli.infra.filemaker_api import FileMakerAPI
from fmcli.services import session_helper
from fmcli.services.query_utils import (
    build_portal_get_params,
    build_portal_post_body,
    parse_portal_params,
    parse_script_params,
    parse_sort,
    resolve_query,
)
from fmcli.services.session_helper import call_with_refresh

logger = logging.getLogger(__name__)


class _ParsedParams(NamedTuple):
    """共通パラメータのパース結果."""

    response_fields: list[str] | None
    portal_params: dict[str, Any] | None
    script_params: dict[str, str] | None


def _extract_records(body: dict[str, Any]) -> tuple[list[Any], Pagination]:
    response = body.get("response", {})
    data = response.get("data", [])
    data_info = response.get("dataInfo", {})
    pagination = Pagination(
        total_count=data_info.get("totalRecordCount", 0),
        found_count=data_info.get("foundCount", 0),
        returned_count=data_info.get("returnedCount", len(data)),
    )
    return data, pagination


def _extract_script_results(body: dict[str, Any]) -> dict[str, Any] | None:
    """スクリプト実行結果を API レスポンスから抽出する."""
    response = body.get("response", {})
    results: dict[str, Any] = {}
    for key in (
        "scriptResult",
        "scriptError",
        "scriptResult.presort",
        "scriptError.presort",
        "scriptResult.prerequest",
        "scriptError.prerequest",
    ):
        if key in response:
            results[key] = response[key]
    return results or None


def _attach_script_results(envelope: Envelope, script_results: dict[str, Any] | None) -> None:
    """スクリプト実行結果を Envelope に構造化データとして付与する."""
    if not script_results:
        return
    envelope.script_results = script_results
    # scriptError が非ゼロの場合は警告メッセージを追加
    for key in ("scriptError", "scriptError.presort", "scriptError.prerequest"):
        error_code = script_results.get(key, "0")
        if str(error_code) != "0":
            envelope.messages.append(f"スクリプトエラー ({key}): code {error_code}")


def _parse_fields(fields: str | None) -> list[str] | None:
    """カンマ区切りのフィールド指定をリストに変換する."""
    if not fields:
        return None
    return [f.strip() for f in fields.split(",") if f.strip()]


def _parse_common_params(
    fields: str | None,
    portal: str | None,
    script: str | None,
    script_presort: str | None,
    script_prerequest: str | None,
) -> _ParsedParams:
    """fields / portal / script の共通パース処理."""
    return _ParsedParams(
        response_fields=_parse_fields(fields),
        portal_params=parse_portal_params(portal),
        script_params=parse_script_params(script, script_presort, script_prerequest),
    )


def _filter_record_fields(records: list[Any], fields: list[str] | None) -> list[Any]:
    """レコード配列の fieldData を指定フィールドのみに絞る."""
    if not fields:
        return records

    allowed = set(fields)
    filtered_records: list[Any] = []
    for record in records:
        if not isinstance(record, dict):
            filtered_records.append(record)
            continue

        filtered = dict(record)
        field_data = filtered.get("fieldData")
        if isinstance(field_data, dict):
            filtered["fieldData"] = {
                key: value for key, value in field_data.items() if key in allowed
            }
        filtered_records.append(filtered)
    return filtered_records


def get_record(
    profile: Profile,
    layout: str,
    record_id: int,
    *,
    fields: str | None = None,
    portal: str | None = None,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """単一レコードを取得する."""
    parsed = _parse_common_params(fields, portal, script, script_presort, script_prerequest)
    get_pp = build_portal_get_params(parsed.portal_params) if parsed.portal_params else None

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.get_record(
            layout,
            record_id,
            portal_params=get_pp,
            script_params=parsed.script_params,
        )

    body, api_info = call_with_refresh(profile, _call)
    data = body.get("response", {}).get("data", [])
    # クライアント側フィールドフィルタ（FM Data API の単一レコード取得は _fields 非対応）
    data = _filter_record_fields(data, parsed.response_fields)
    record = data[0] if data else None
    script_results = _extract_script_results(body)
    envelope = Envelope.from_profile(
        profile,
        command="record get",
        layout=layout,
        data=record,
        api=api_info,
    )
    _attach_script_results(envelope, script_results)
    return envelope


def list_records(
    profile: Profile,
    layout: str,
    *,
    offset: int = 1,
    limit: int = 100,
    sort: str | None = None,
    fields: str | None = None,
    portal: str | None = None,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """レコード一覧を取得する."""
    sort_spec = parse_sort(sort)
    parsed = _parse_common_params(fields, portal, script, script_presort, script_prerequest)
    get_pp = build_portal_get_params(parsed.portal_params) if parsed.portal_params else None

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.get_records(
            layout,
            offset=offset,
            limit=limit,
            sort=sort_spec,
            portal_params=get_pp,
            script_params=parsed.script_params,
        )

    body, api_info = call_with_refresh(profile, _call)
    data, pagination = _extract_records(body)
    data = _filter_record_fields(data, parsed.response_fields)
    pagination = pagination.model_copy(update={"offset": offset, "limit": limit})
    script_results = _extract_script_results(body)
    envelope = Envelope.from_profile(
        profile,
        command="record list",
        layout=layout,
        data=data,
        pagination=pagination,
        api=api_info,
    )
    _attach_script_results(envelope, script_results)
    return envelope


def find_records(
    profile: Profile,
    layout: str,
    *,
    query: str | None = None,
    query_file: str | None = None,
    offset: int = 1,
    limit: int = 100,
    sort: str | None = None,
    fields: str | None = None,
    count_only: bool = False,
    portal: str | None = None,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """レコードを検索する."""
    query_data = resolve_query(query, query_file)
    sort_spec = parse_sort(sort)
    parsed = _parse_common_params(fields, portal, script, script_presort, script_prerequest)
    post_pp = build_portal_post_body(parsed.portal_params) if parsed.portal_params else None

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.find_records(
            layout,
            query_data,
            offset=offset,
            limit=limit,
            sort=sort_spec,
            portal_params=post_pp,
            script_params=parsed.script_params,
        )

    try:
        body, api_info = call_with_refresh(profile, _call)
    except ApiError as e:
        if e.api_code == FmApiCode.NO_RECORDS_MATCH:
            # FileMaker は検索結果 0 件を HTTP 500 + api_code 402 (NO_RECORDS_MATCH) で返す。
            # CLI 利用者にとっては空配列が自然なので正規化する。
            _empty_msg = f"該当レコードなし (FileMaker api_code: {e.api_code})"
            _empty_pagination = Pagination(
                total_count=0,
                found_count=0,
                returned_count=0,
                offset=offset,
                limit=limit,
            )
            command = "record find --count" if count_only else "record find"
            data: dict[str, int] | list[Any] = {"found_count": 0} if count_only else []
            return Envelope.from_profile(
                profile,
                command=command,
                layout=layout,
                data=data,
                pagination=_empty_pagination,
                messages=[_empty_msg],
            )
        raise

    data, pagination = _extract_records(body)
    data = _filter_record_fields(data, parsed.response_fields)
    pagination = pagination.model_copy(update={"offset": offset, "limit": limit})
    script_results = _extract_script_results(body)

    command = "record find --count" if count_only else "record find"
    result_data: Any = {"found_count": pagination.found_count} if count_only else data
    envelope = Envelope.from_profile(
        profile,
        command=command,
        layout=layout,
        data=result_data,
        pagination=pagination,
        api=api_info,
    )

    _attach_script_results(envelope, script_results)
    return envelope


def validate_container_field(
    profile: Profile,
    layout: str,
    field_name: str,
) -> bool:
    """フィールドがコンテナ型であるか検証する.

    Returns:
        True ならコンテナ型。メタデータ取得に失敗した場合は True（検証スキップ）。
    """
    from fmcli.services.metadata_service import layout_describe

    envelope = layout_describe(profile, layout)
    if not envelope.ok:
        logger.warning("コンテナ検証スキップ: レイアウト '%s' のメタデータ取得に失敗", layout)
        return True
    for f in envelope.data.get("fieldMetaData", []):
        if f.get("name") == field_name:
            is_container: bool = f.get("result") == "container"
            return is_container
    # フィールドが見つからない場合は False
    return False


def upload_container(
    profile: Profile,
    layout: str,
    record_id: int,
    *,
    field_name: str,
    file_path: str,
    file_name: str,
    mime_type: str,
    repetition: int = 1,
    if_mod_id: str | None = None,
) -> Envelope:
    """コンテナフィールドにファイルをアップロードする."""
    # --if-mod-id による事前検証
    if if_mod_id is not None:
        current = fetch_record_for_update(profile, layout, record_id)
        current_mod_id = current.get("modId", "")
        if current_mod_id != if_mod_id:
            raise ApiError(
                f"modId が一致しません (指定: {if_mod_id}, 現在: {current_mod_id})。"
                f"\n他のユーザーがレコードを更新した可能性があります。"
                f"\n最新の modId を取得してリトライ: "
                f"`fmcli record get {record_id} -l '{layout}'`",
                http_status=409,
                api_code=0,
            )

    file_size = os.path.getsize(file_path)

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.upload_container(
            layout,
            record_id,
            field_name,
            file_path=file_path,
            file_name=file_name,
            mime_type=mime_type,
            repetition=repetition,
        )

    body, api_info = call_with_refresh(profile, _call)

    result: dict[str, Any] = {
        "recordId": str(record_id),
        "field": field_name,
        "repetition": repetition,
        "file": file_name,
        "file_size": file_size,
        "mime_type": mime_type,
    }

    envelope = Envelope.from_profile(
        profile,
        command="record upload",
        layout=layout,
        data=result,
        api=api_info,
    )
    # スクリプト結果の抽出（upload API もスクリプト結果を返す可能性がある）
    script_results = _extract_script_results(body)
    _attach_script_results(envelope, script_results)
    return envelope


def validate_field_names(
    profile: Profile,
    layout: str,
    field_data: dict[str, Any],
) -> list[str]:
    """フィールド名をレイアウトメタデータと照合し、不正なフィールド名を返す."""
    from fmcli.services.metadata_service import layout_describe

    envelope = layout_describe(profile, layout)
    if not envelope.ok:
        logger.warning("フィールド検証スキップ: レイアウト '%s' のメタデータ取得に失敗", layout)
        return []
    known_fields = {f.get("name", "") for f in envelope.data.get("fieldMetaData", [])}
    return [name for name in field_data if name not in known_fields]


def create_record(
    profile: Profile,
    layout: str,
    *,
    field_data: dict[str, Any],
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """レコードを作成する.

    field_data は CLI 層で resolve_field_data() 済みの dict を受け取る。
    """
    script_params = parse_script_params(script, script_presort, script_prerequest)

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.create_record(
            layout,
            field_data,
            script_params=script_params,
        )

    body, api_info = call_with_refresh(profile, _call)
    response = body.get("response", {})
    result = {
        "recordId": response.get("recordId", ""),
        "modId": response.get("modId", ""),
    }
    script_results = _extract_script_results(body)
    envelope = Envelope.from_profile(
        profile,
        command="record create",
        layout=layout,
        data=result,
        api=api_info,
    )
    _attach_script_results(envelope, script_results)
    return envelope


def fetch_record_for_update(
    profile: Profile,
    layout: str,
    record_id: int,
) -> dict[str, Any]:
    """更新前のレコードを取得する (modId 検証・diff 表示用)."""

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.get_record(layout, record_id)

    body, _ = call_with_refresh(profile, _call)
    data = body.get("response", {}).get("data", [])
    if not data:
        from fmcli.core.errors import NotFoundError

        raise NotFoundError(f"レコード {record_id} が見つかりません。")
    record: dict[str, Any] = data[0]
    return record


def update_record(
    profile: Profile,
    layout: str,
    record_id: int,
    *,
    field_data: dict[str, Any],
    mod_id: str,
    prefetched_record: dict[str, Any],
    no_backup: bool = False,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """レコードを更新する.

    prefetched_record は CLI 層で fetch_record_for_update() 済みのレコードを受け取る。
    1. modId を検証
    2. PATCH API で更新
    3. undo 情報を保存
    """
    current_mod_id = prefetched_record.get("modId", "")
    current_field_data = prefetched_record.get("fieldData", {})

    if current_mod_id != mod_id:
        raise ApiError(
            f"modId が一致しません (指定: {mod_id}, 現在: {current_mod_id})。"
            f"\n他のユーザーがレコードを更新した可能性があります。"
            f"\n最新の modId を取得してリトライ: "
            f"`fmcli record get {record_id} -l '{layout}'`",
            http_status=409,
            api_code=0,
        )

    # 2. PATCH API で更新
    script_params = parse_script_params(script, script_presort, script_prerequest)

    def _call(api: FileMakerAPI) -> session_helper.ApiResult:
        return api.update_record(
            layout,
            record_id,
            field_data,
            mod_id=mod_id,
            script_params=script_params,
        )

    body, api_info = call_with_refresh(profile, _call)
    response = body.get("response", {})
    new_mod_id = response.get("modId", "")

    # 3. undo 情報を保存
    undo_file: str | None = None
    updated_fields = list(field_data.keys())
    if not no_backup:
        from fmcli.infra.undo_store import save_undo

        # 更新対象フィールドの変更前の値のみ保存
        before_data = {k: current_field_data.get(k) for k in updated_fields}
        undo_file = save_undo(
            record_id=record_id,
            layout=layout,
            host=profile.host,
            database=profile.database,
            mod_id_before=mod_id,
            mod_id_after=new_mod_id,
            field_data_before=before_data,
            updated_fields=updated_fields,
        )
        if undo_file is None:
            logger.warning("undo 情報の保存に失敗しましたが、更新は成功しています。")

    messages: list[str] = []
    if not no_backup and undo_file is None:
        messages.append("Warning: undo 情報の保存に失敗しました。更新は成功しています。")

    result: dict[str, Any] = {
        "recordId": str(record_id),
        "modId": new_mod_id,
        "previous_modId": mod_id,
        "updated_fields": updated_fields,
    }
    if undo_file:
        result["undo_file"] = undo_file

    script_results = _extract_script_results(body)
    envelope = Envelope.from_profile(
        profile,
        command="record update",
        layout=layout,
        data=result,
        api=api_info,
        messages=messages,
    )
    _attach_script_results(envelope, script_results)
    return envelope
