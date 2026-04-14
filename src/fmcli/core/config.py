"""設定読み込みと優先順位管理."""

from __future__ import annotations

import os
from pathlib import Path

_XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_XDG_CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

DEFAULT_CONFIG_DIR = _XDG_CONFIG_HOME / "fmcli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_PROFILES_DIR = DEFAULT_CONFIG_DIR / "profiles"
DEFAULT_CACHE_DIR = _XDG_CACHE_HOME / "fmcli"
