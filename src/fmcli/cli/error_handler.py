"""CLI 層のエラーハンドリングデコレータ."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

import typer

from fmcli.core.errors import (
    EXIT_GENERAL,
    EXIT_INPUT,
    EXIT_INTERRUPT,
    FmcliError,
    build_error_envelope,
    emit_error_envelope,
)
from fmcli.domain.envelopes import Envelope, ErrorDetail

logger = logging.getLogger(__name__)


def handle_errors(command_name: str = "") -> Callable[..., Any]:
    """CLI コマンドの共通エラーハンドリングデコレータ."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except (KeyboardInterrupt, typer.Abort):
                raise typer.Exit(EXIT_INTERRUPT) from None
            except typer.BadParameter as exc:
                logger.warning("%s: %s", type(exc).__name__, exc)
                detail = ErrorDetail(
                    type="input_error",
                    message=exc.format_message(),
                    hint="入力値を確認してください",
                )
                envelope = Envelope(ok=False, command=command_name, error=detail)
                emit_error_envelope(envelope)
                raise typer.Exit(EXIT_INPUT) from None
            except (FmcliError, ValueError) as exc:
                logger.warning("%s: %s", type(exc).__name__, exc)
                envelope = build_error_envelope(exc, command=command_name)
                emit_error_envelope(envelope)
                code = exc.exit_code if isinstance(exc, FmcliError) else EXIT_INPUT
                raise typer.Exit(code) from None
            except typer.Exit:
                raise
            except Exception as exc:
                logger.warning("unexpected: %s: %s", type(exc).__name__, exc)
                envelope = build_error_envelope(exc, command=command_name)
                emit_error_envelope(envelope)
                raise typer.Exit(EXIT_GENERAL) from None

        return wrapper

    return decorator
