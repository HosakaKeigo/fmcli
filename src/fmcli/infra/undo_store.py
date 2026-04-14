"""undo ファイルの保存・読み込み."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_UNDO_DIR_NAME = "undo"


def _get_undo_dir() -> Path:
    """undo ディレクトリのパスを返す."""
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "fmcli" / _UNDO_DIR_NAME


def save_undo(
    *,
    record_id: int,
    layout: str,
    host: str,
    database: str,
    mod_id_before: str,
    mod_id_after: str,
    field_data_before: dict[str, Any],
    updated_fields: list[str],
) -> str | None:
    """undo 情報をファイルに保存する.

    Returns:
        保存先のファイルパス。保存失敗時は None。
    """
    undo_dir = _get_undo_dir()
    try:
        undo_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(undo_dir, 0o700)
    except OSError as e:
        logger.warning("undo ディレクトリの作成に失敗: %s", e)
        return None

    now = datetime.now(tz=UTC)
    filename = f"{now.strftime('%Y%m%d_%H%M%S_%f')}_{record_id}.json"
    filepath = undo_dir / filename

    undo_data = {
        "timestamp": now.isoformat(),
        "record_id": record_id,
        "layout": layout,
        "host": host,
        "database": database,
        "mod_id_before": mod_id_before,
        "mod_id_after": mod_id_after,
        "field_data_before": field_data_before,
        "updated_fields": updated_fields,
    }

    try:
        filepath.write_text(json.dumps(undo_data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(filepath, 0o600)
    except OSError as e:
        logger.warning("undo ファイルの保存に失敗: %s", e)
        return None

    return str(filepath)
