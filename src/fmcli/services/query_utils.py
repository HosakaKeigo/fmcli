"""クエリ / ソート解析ユーティリティ."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fmcli.core.compat import read_text_utf8

_VALID_SORT_ORDERS = {"ascend", "descend"}
_SORT_ALIASES: dict[str, str] = {"asc": "ascend", "desc": "descend"}


def parse_sort(sort_str: str | None) -> list[dict[str, str]] | None:
    """ソート指定をパースする. 例: 'Name:ascend,Age:descend'."""
    if not sort_str:
        return None
    result: list[dict[str, str]] = []
    for part in sort_str.split(","):
        parts = part.strip().split(":")
        field = parts[0].strip()
        order = parts[1] if len(parts) > 1 else "ascend"
        order = _SORT_ALIASES.get(order, order)
        if order not in _VALID_SORT_ORDERS:
            raise ValueError(f"無効なソート順: {order!r} (有効: ascend, descend, asc, desc)")
        result.append({"fieldName": field, "sortOrder": order})
    return result


def parse_portal_params(
    portal_spec: str | None,
) -> dict[str, Any] | None:
    """ポータル指定文字列をパースする.

    Format: "PortalName" or "Portal1,Portal2" or "Portal1:10,Portal2:5:2"
    各ポータル名の後に :limit や :limit:offset を付加できる。

    Returns dict with:
      - "portal": list of portal names
      - "limit.<name>": limit per portal (if specified)
      - "offset.<name>": offset per portal (if specified)
    """
    if not portal_spec:
        return None

    result: dict[str, Any] = {}
    portal_names: list[str] = []

    for part in portal_spec.split(","):
        part = part.strip()
        if not part:
            continue
        # Split from the right to handle portal names that may contain ":"
        # Format: PortalName or PortalName:limit or PortalName:limit:offset
        # We try to parse trailing numeric segments as limit/offset
        segments = part.split(":")
        # Find where the numeric suffix starts
        name_parts: list[str] = []
        numeric_parts: list[str] = []
        # Walk from end to find numeric segments
        i = len(segments) - 1
        while i > 0 and segments[i].isdigit():
            numeric_parts.insert(0, segments[i])
            i -= 1
        name_parts = segments[: i + 1]
        name = ":".join(name_parts)
        if not name:
            continue
        portal_names.append(name)
        if len(numeric_parts) >= 1:
            result[f"limit.{name}"] = numeric_parts[0]
        if len(numeric_parts) >= 2:
            result[f"offset.{name}"] = numeric_parts[1]

    if not portal_names:
        return None

    result["portal"] = portal_names
    return result


def build_portal_get_params(portal_params: dict[str, Any]) -> dict[str, str]:
    """GET リクエスト用のポータルクエリパラメータを構築する.

    GET では portal は JSON 配列、offset/limit にはアンダースコアプレフィックスを付ける。
    """
    params: dict[str, str] = {}
    params["portal"] = json.dumps(portal_params["portal"])
    for key, value in portal_params.items():
        if key == "portal":
            continue
        if key.startswith("limit."):
            portal_name = key[len("limit.") :]
            params[f"_limit.{portal_name}"] = str(value)
        elif key.startswith("offset."):
            portal_name = key[len("offset.") :]
            params[f"_offset.{portal_name}"] = str(value)
    return params


def build_portal_post_body(portal_params: dict[str, Any]) -> dict[str, Any]:
    """POST リクエスト用のポータルボディパラメータを構築する.

    POST では portal はリスト、offset/limit にはプレフィックスなし。
    """
    body: dict[str, Any] = {}
    body["portal"] = portal_params["portal"]
    for key, value in portal_params.items():
        if key == "portal":
            continue
        # POST body の limit/offset は int で送る
        body[key] = int(value)
    return body


def parse_script_params(
    script: str | None,
    script_presort: str | None = None,
    script_prerequest: str | None = None,
) -> dict[str, str] | None:
    """スクリプト実行パラメータをパースする.

    各スクリプト指定のフォーマット: "ScriptName" または "ScriptName:param"

    Returns dict with FileMaker API keys:
      - "script": script name (after sort)
      - "script.param": script param
      - "script.presort": presort script name
      - "script.presort.param": presort script param
      - "script.prerequest": prerequest script name
      - "script.prerequest.param": prerequest script param
    Only non-None entries are included.
    """
    if not any([script, script_presort, script_prerequest]):
        return None

    result: dict[str, str] = {}

    for spec, name_key, param_key in [
        (script, "script", "script.param"),
        (script_presort, "script.presort", "script.presort.param"),
        (script_prerequest, "script.prerequest", "script.prerequest.param"),
    ]:
        if not spec:
            continue
        # Split on first ":" only to allow params containing ":"
        parts = spec.split(":", 1)
        name = parts[0].strip()
        if not name:
            msg = f"スクリプト名が空です: {spec!r}"
            raise ValueError(msg)
        result[name_key] = name
        if len(parts) > 1:
            result[param_key] = parts[1]

    return result or None


def resolve_field_data(
    field_data: str | None,
    field_data_file: str | None,
) -> dict[str, Any]:
    """--field-data または --field-data-file からフィールドデータを解決する.

    両方指定時は --field-data-file を優先（resolve_query と同じポリシー）。
    どちらも未指定はエラー。
    """
    if field_data_file:
        if field_data_file.startswith("@"):
            field_data_file = field_data_file[1:]
        resolved = os.path.realpath(field_data_file)
        if not resolved.endswith(".json"):
            raise ValueError(
                f"フィールドデータファイルは .json 拡張子が必要です: {field_data_file}"
            )
        try:
            text = read_text_utf8(Path(resolved))
        except FileNotFoundError:
            raise ValueError(
                f"フィールドデータファイルが見つかりません: {field_data_file}"
            ) from None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"フィールドデータファイルの JSON が不正です: {field_data_file}\n{e}"
            ) from None
    elif field_data:
        try:
            raw = json.loads(field_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"--field-data の JSON が不正です: {e}") from None
    else:
        raise ValueError("--field-data または --field-data-file が必要です")

    if not isinstance(raw, dict):
        raise ValueError("フィールドデータは JSON オブジェクトである必要があります")

    return raw


def resolve_query(
    query: str | None,
    query_file: str | None,
) -> list[dict[str, Any]]:
    """クエリ文字列またはファイルから検索条件を解決する."""
    if query_file:
        if query_file.startswith("@"):
            query_file = query_file[1:]
        resolved = os.path.realpath(query_file)
        if not resolved.endswith(".json"):
            raise ValueError(f"クエリファイルは .json 拡張子が必要です: {query_file}")
        try:
            text = read_text_utf8(Path(resolved))
        except FileNotFoundError:
            raise ValueError(f"クエリファイルが見つかりません: {query_file}") from None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"クエリファイルの JSON が不正です: {query_file}\n{e}") from None
    elif query:
        try:
            raw = json.loads(query)
        except json.JSONDecodeError as e:
            raise ValueError(f"--query の JSON が不正です: {e}") from None
    else:
        raise ValueError("--query または --query-file のいずれかが必要です")

    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return [raw]
    raise ValueError("Query must be a JSON object or array of objects")
