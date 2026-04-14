"""ドメイン共有型定義."""

from __future__ import annotations

from typing import Literal

AuthScope = Literal["database", "host"]
StatusScope = Literal["auto", "database", "host"]
