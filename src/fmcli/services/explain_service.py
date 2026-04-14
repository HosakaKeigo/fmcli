"""explain / dry-run / schema サービス."""

from __future__ import annotations

import json
from typing import Any

from fmcli.core.dry_run import build_dry_run
from fmcli.domain.envelopes import Envelope
from fmcli.domain.models import Profile
from fmcli.infra.filemaker_api import FMDATA_API_BASE, FileMakerAPI
from fmcli.infra.session_cache import get_cached_token
from fmcli.services.query_utils import (
    build_portal_get_params,
    build_portal_post_body,
    parse_portal_params,
    parse_script_params,
    parse_sort,
    resolve_query,
)


def dry_run_find(
    profile: Profile,
    layout: str,
    *,
    query: str | None = None,
    query_file: str | None = None,
    offset: int = 1,
    limit: int = 100,
    sort: str | None = None,
    fields: str | None = None,
    portal: str | None = None,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """find の dry-run を実行する."""
    token = get_cached_token(profile) or "NO_TOKEN"
    query_data = resolve_query(query, query_file)
    sort_spec = parse_sort(sort)

    body: dict[str, Any] = {"query": query_data}
    if sort_spec:
        body["sort"] = sort_spec
    body["offset"] = str(offset)
    body["limit"] = str(limit)

    pp = parse_portal_params(portal)
    if pp:
        body.update(build_portal_post_body(pp))

    sp = parse_script_params(script, script_presort, script_prerequest)
    if sp:
        body.update(sp)

    path = FileMakerAPI.build_find_path(profile.database, layout)

    dry = build_dry_run(
        method="POST",
        host=profile.host,
        path=path,
        token=token,
        body=body,
    )

    messages = ["Dry run: no request was sent"]
    if fields:
        messages.append("Note: --fields is applied client-side after _find results are returned.")

    return Envelope.from_profile(
        profile,
        command="record find --dry-run",
        layout=layout,
        data=dry.model_dump(),
        messages=messages,
    )


def dry_run_record_list(
    profile: Profile,
    layout: str,
    *,
    offset: int = 1,
    limit: int = 100,
    sort: str | None = None,
    portal: str | None = None,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """record list の dry-run を実行する."""
    token = get_cached_token(profile) or "NO_TOKEN"
    sort_spec = parse_sort(sort)

    path = FileMakerAPI.build_records_path(profile.database, layout)
    params: list[str] = [f"_offset={offset}", f"_limit={limit}"]
    if sort_spec:
        params.append(f"_sort={json.dumps(sort_spec)}")

    pp = parse_portal_params(portal)
    if pp:
        get_pp = build_portal_get_params(pp)
        for key, value in get_pp.items():
            params.append(f"{key}={value}")

    sp = parse_script_params(script, script_presort, script_prerequest)
    if sp:
        for key, value in sp.items():
            params.append(f"{key}={value}")

    path = f"{path}?{'&'.join(params)}"

    dry = build_dry_run(method="GET", host=profile.host, path=path, token=token)

    return Envelope.from_profile(
        profile,
        command="record list --dry-run",
        layout=layout,
        data=dry.model_dump(),
        messages=["Dry run: no request was sent"],
    )


def dry_run_create(
    profile: Profile,
    layout: str,
    *,
    field_data: dict[str, Any],
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """record create の dry-run を実行する.

    field_data は CLI 層で resolve_field_data() 済みの dict を受け取る。
    API 呼び出しは一切行わない。
    """
    token = get_cached_token(profile) or "NO_TOKEN"

    body: dict[str, Any] = {"fieldData": field_data}

    sp = parse_script_params(script, script_presort, script_prerequest)
    if sp:
        body.update(sp)

    path = FileMakerAPI.build_records_path(profile.database, layout)

    dry = build_dry_run(
        method="POST",
        host=profile.host,
        path=path,
        token=token,
        body=body,
    )

    return Envelope.from_profile(
        profile,
        command="record create --dry-run",
        layout=layout,
        data=dry.model_dump(),
        messages=["Dry run: no request was sent"],
    )


def dry_run_update(
    profile: Profile,
    layout: str,
    record_id: int,
    *,
    field_data: dict[str, Any],
    mod_id: str,
    script: str | None = None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> Envelope:
    """record update の dry-run を実行する.

    field_data は CLI 層で resolve_field_data() 済みの dict を受け取る。
    API 呼び出しは一切行わない。
    """
    token = get_cached_token(profile) or "NO_TOKEN"
    from fmcli.core.encoding import encode_fm_value

    db = encode_fm_value(profile.database)
    lay = encode_fm_value(layout)
    path = f"{FMDATA_API_BASE}/databases/{db}/layouts/{lay}/records/{record_id}"

    body: dict[str, Any] = {"fieldData": field_data, "modId": mod_id}

    sp = parse_script_params(script, script_presort, script_prerequest)
    if sp:
        body.update(sp)

    dry = build_dry_run(
        method="PATCH",
        host=profile.host,
        path=path,
        token=token,
        body=body,
    )

    return Envelope.from_profile(
        profile,
        command="record update --dry-run",
        layout=layout,
        data=dry.model_dump(),
        messages=["Dry run: no request was sent"],
    )


def dry_run_upload(
    profile: Profile,
    layout: str,
    record_id: int,
    *,
    field_name: str,
    file_path: str,
    file_name: str,
    file_size: int,
    mime_type: str,
    repetition: int = 1,
) -> Envelope:
    """record upload の dry-run を実行する.

    API 呼び出しは一切行わない。multipart の生データではなく意味的プレビューを返す。
    """
    token = get_cached_token(profile) or "NO_TOKEN"
    from fmcli.core.encoding import encode_fm_value

    db = encode_fm_value(profile.database)
    lay = encode_fm_value(layout)
    field = encode_fm_value(field_name)
    path = (
        f"{FMDATA_API_BASE}/databases/{db}"
        f"/layouts/{lay}/records/{record_id}"
        f"/containers/{field}/{repetition}"
    )

    from fmcli.core.masking import mask_token

    url = f"{profile.host.rstrip('/')}{path}"
    data = {
        "method": "POST",
        "url": url,
        "headers": {
            "Authorization": f"Bearer {mask_token(token)}",
            "Content-Type": "multipart/form-data (boundary auto-generated)",
        },
        "body": {
            "upload": {
                "file": file_name,
                "path": file_path,
                "size": file_size,
                "mime_type": mime_type,
            },
        },
        "target": {
            "recordId": str(record_id),
            "field": field_name,
            "repetition": repetition,
        },
    }

    return Envelope.from_profile(
        profile,
        command="record upload --dry-run",
        layout=layout,
        data=data,
        messages=["Dry run: no request was sent"],
    )


def explain_find(
    profile: Profile,
    layout: str,
    *,
    query: str | None = None,
    query_file: str | None = None,
    offset: int = 1,
    limit: int = 100,
    sort: str | None = None,
) -> Envelope:
    """find クエリの説明を生成する."""
    query_data = resolve_query(query, query_file)
    sort_spec = parse_sort(sort)

    explanations: list[str] = []
    explanations.append(f"Target: layout '{layout}' in database '{profile.database}'")
    explanations.append(f"API endpoint: POST /_find on layout '{layout}'")

    for i, condition in enumerate(query_data):
        fields = ", ".join(f"{k}={v!r}" for k, v in condition.items())
        explanations.append(f"Condition {i + 1}: {fields}")

    if len(query_data) > 1:
        explanations.append(
            f"Logic: {len(query_data)} conditions combined with OR (FileMaker find behavior)"
        )

    if sort_spec:
        sort_desc = ", ".join(f"{s['fieldName']} {s['sortOrder']}" for s in sort_spec)
        explanations.append(f"Sort: {sort_desc}")

    explanations.append(f"Pagination: offset={offset}, limit={limit}")

    return Envelope.from_profile(
        profile,
        command="explain find",
        layout=layout,
        data={"explanation": explanations, "query": query_data},
    )


def _deduplicate_by_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """name キーで重複除去する（出現順を維持）."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        name = item.get("name", "")
        if name not in seen:
            seen.add(name)
            result.append(item)
    return result


def schema_find(profile: Profile, layout: str) -> Envelope:
    """find に使えるフィールド候補を layout metadata から取得する."""
    from fmcli.services.metadata_service import layout_describe

    meta_envelope = layout_describe(profile, layout)
    if not meta_envelope.ok:
        return meta_envelope

    fields_meta = meta_envelope.data.get("fieldMetaData", [])
    find_fields = []
    for f in fields_meta:
        find_fields.append(
            {
                "name": f.get("name", ""),
                "type": f.get("result", ""),
                "global": f.get("global", False),
            }
        )

    portal_meta = meta_envelope.data.get("portalMetaData", {})
    portals = []
    for portal_name, portal_fields in portal_meta.items():
        portals.append(
            {
                "portal": portal_name,
                "fields": [
                    {"name": pf.get("name", ""), "type": pf.get("result", "")}
                    for pf in portal_fields
                ],
            }
        )

    return Envelope.from_profile(
        profile,
        command="schema find",
        layout=layout,
        data={
            "findable_fields": _deduplicate_by_name(find_fields),
            "portals": portals,
            "value_lists": _deduplicate_by_name(meta_envelope.data.get("valueLists", [])),
        },
    )


def schema_output(profile: Profile, layout: str) -> Envelope:
    """layout の出力構造を取得する."""
    from fmcli.services.metadata_service import layout_describe

    meta_envelope = layout_describe(profile, layout)
    if not meta_envelope.ok:
        return meta_envelope

    fields_meta = meta_envelope.data.get("fieldMetaData", [])
    field_names = [f.get("name", "") for f in fields_meta]

    portal_meta = meta_envelope.data.get("portalMetaData", {})
    portal_structure: dict[str, list[str]] = {}
    for portal_name, portal_fields in portal_meta.items():
        portal_structure[portal_name] = [pf.get("name", "") for pf in portal_fields]

    return Envelope.from_profile(
        profile,
        command="schema output",
        layout=layout,
        data={
            "fieldData_keys": field_names,
            "portalData": portal_structure,
        },
    )
