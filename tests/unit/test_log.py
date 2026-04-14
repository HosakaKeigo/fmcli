"""ロギング設定のテスト."""

from __future__ import annotations

import logging

import pytest

from fmcli.core.log import setup_logging


@pytest.fixture(autouse=True)
def _cleanup_logger():
    """テスト間でロガーの状態をリセットする."""
    root = logging.getLogger("fmcli")
    original_handlers = root.handlers[:]
    original_level = root.level
    # テスト前にクリア（他テストで設定された NullHandler 等を除去）
    root.handlers.clear()
    root.level = logging.WARNING
    yield
    root.handlers = original_handlers
    root.level = original_level


class TestSetupLogging:
    def test_verbose_true_adds_handler(self) -> None:
        root = logging.getLogger("fmcli")
        assert len(root.handlers) == 0

        setup_logging(verbose=True)

        assert len(root.handlers) == 1
        assert root.level == logging.DEBUG
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)

    def test_verbose_false_adds_null_handler(self) -> None:
        """非 verbose 時は NullHandler で lastResort を抑制する."""
        root = logging.getLogger("fmcli")
        assert len(root.handlers) == 0

        setup_logging(verbose=False)

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.NullHandler)

    def test_idempotent(self) -> None:
        """2回呼んでも handler が重複しない."""
        setup_logging(verbose=True)
        setup_logging(verbose=True)

        root = logging.getLogger("fmcli")
        assert len(root.handlers) == 1

    def test_child_logger_propagates(self) -> None:
        """子ロガーのメッセージが fmcli ロガーに伝播する."""
        setup_logging(verbose=True)

        child = logging.getLogger("fmcli.infra.http_client")
        root = logging.getLogger("fmcli")

        assert child.getEffectiveLevel() == logging.DEBUG
        assert root.handlers[0] in child.parent.handlers  # type: ignore[union-attr]

    def test_format_contains_fmcli_prefix(self, capfd: pytest.CaptureFixture[str]) -> None:
        """ログ出力に [fmcli] プレフィックスが含まれる."""
        setup_logging(verbose=True)

        child = logging.getLogger("fmcli.test")
        child.debug("test message")

        captured = capfd.readouterr()
        assert "[fmcli]" in captured.err
        assert "test message" in captured.err
