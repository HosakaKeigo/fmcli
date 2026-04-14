"""ロギング設定."""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "[fmcli] %(levelname)s %(name)s - %(message)s"


def setup_logging(verbose: bool) -> None:
    """verbose 時のみ stderr に DEBUG ログを出力する.

    非 verbose 時は NullHandler を設定して lastResort による
    stderr 汚染を防止する。
    """
    root = logging.getLogger("fmcli")
    if root.handlers:
        return

    if not verbose:
        root.addHandler(logging.NullHandler())
        return

    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)
