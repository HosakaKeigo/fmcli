"""グローバル設定の永続化ストア.

~/.config/fmcli/config.json に設定を保存・読み込みする。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fmcli.core.output import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# 設定可能なキーとバリデーション
VALID_KEYS: dict[str, str] = {
    "timeout": "API タイムアウト秒数 (正の整数)",
}

# 各キーのデフォルト値
DEFAULTS: dict[str, Any] = {
    "timeout": DEFAULT_TIMEOUT,
}


def _validate(key: str, value: str) -> Any:
    """キーに応じた型変換・バリデーションを行い、変換後の値を返す."""
    if key == "timeout":
        try:
            v = int(value)
        except ValueError:
            raise ValueError(f"timeout は正の整数で指定してください: {value!r}") from None
        if v < 1:
            raise ValueError(f"timeout は 1 以上で指定してください: {v}")
        return v
    raise ValueError(f"不明な設定キー: {key!r}")


def _config_path() -> Path:
    """設定ファイルのパスを返す（遅延評価でテスト時のパッチに対応）."""
    from fmcli.core.config import DEFAULT_CONFIG_FILE

    return DEFAULT_CONFIG_FILE


def _read_config() -> dict[str, Any]:
    """config.json を読み込む。存在しなければ空 dict を返す."""
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("config.json の読み込みに失敗: %s", e)
        return {}
    if not isinstance(loaded, dict):
        logger.warning("config.json が不正な形式です: %s", type(loaded).__name__)
        return {}
    return loaded


def _write_config(data: dict[str, Any]) -> None:
    """config.json にアトミックに書き込む."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def config_set(key: str, value: str) -> Any:
    """設定値を保存し、変換後の値を返す."""
    if key not in VALID_KEYS:
        raise ValueError(f"不明な設定キー: {key!r} (有効なキー: {', '.join(VALID_KEYS)})")
    converted = _validate(key, value)
    data = _read_config()
    data[key] = converted
    _write_config(data)
    return converted


def _is_valid_value(key: str, value: Any) -> bool:
    """保存済みの値が有効かチェックする（手編集対策）."""
    if key == "timeout":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1
    return False


def config_get(key: str) -> Any | None:
    """設定値を取得する。未設定または不正値の場合は None を返す."""
    if key not in VALID_KEYS:
        raise ValueError(f"不明な設定キー: {key!r} (有効なキー: {', '.join(VALID_KEYS)})")
    data = _read_config()
    value = data.get(key)
    if value is not None and not _is_valid_value(key, value):
        logger.warning("config.json の %s の値が不正です: %r", key, value)
        return None
    return value


def config_get_effective(key: str) -> Any:
    """設定値を取得する。未設定の場合はデフォルト値を返す."""
    value = config_get(key)
    if value is not None:
        return value
    return DEFAULTS[key]


def config_list() -> dict[str, Any]:
    """全設定を返す."""
    return _read_config()


def config_unset(key: str) -> bool:
    """設定を削除する。削除した場合は True を返す."""
    if key not in VALID_KEYS:
        raise ValueError(f"不明な設定キー: {key!r} (有効なキー: {', '.join(VALID_KEYS)})")
    data = _read_config()
    if key not in data:
        return False
    del data[key]
    _write_config(data)
    return True
