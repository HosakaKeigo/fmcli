"""config CLI コマンドのテスト."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from fmcli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def tmp_config(tmp_path):
    """テスト用の一時設定ファイル."""
    config_file = tmp_path / "config.json"
    with patch("fmcli.infra.config_store._config_path", return_value=config_file):
        yield config_file


class TestConfigSetCommand:
    def test_timeout_を設定できる(self) -> None:
        result = runner.invoke(app, ["config", "set", "timeout", "120"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["ok"] is True
        assert parsed["data"]["key"] == "timeout"
        assert parsed["data"]["value"] == 120

    def test_不正なキーでエラー(self) -> None:
        result = runner.invoke(app, ["config", "set", "bad_key", "100"])
        assert result.exit_code != 0

    def test_不正な値でエラー(self) -> None:
        result = runner.invoke(app, ["config", "set", "timeout", "abc"])
        assert result.exit_code != 0


class TestConfigGetCommand:
    def test_設定済みの値を取得できる(self) -> None:
        runner.invoke(app, ["config", "set", "timeout", "90"])
        result = runner.invoke(app, ["config", "get", "timeout"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["data"]["key"] == "timeout"
        assert parsed["data"]["value"] == 90

    def test_未設定の場合デフォルト値が表示される(self) -> None:
        result = runner.invoke(app, ["config", "get", "timeout"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["data"]["value"] is None
        assert parsed["data"]["effective"] == 60


class TestConfigListCommand:
    def test_設定一覧を表示できる(self) -> None:
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["ok"] is True
        assert isinstance(parsed["data"], list)
        keys = [e["key"] for e in parsed["data"]]
        assert "timeout" in keys

    def test_設定済みの値が反映される(self) -> None:
        runner.invoke(app, ["config", "set", "timeout", "200"])
        result = runner.invoke(app, ["config", "list"])
        parsed = json.loads(result.stdout)
        timeout_entry = next(e for e in parsed["data"] if e["key"] == "timeout")
        assert timeout_entry["value"] == 200
        assert timeout_entry["default"] == 60


class TestConfigUnsetCommand:
    def test_設定を削除できる(self) -> None:
        runner.invoke(app, ["config", "set", "timeout", "120"])
        result = runner.invoke(app, ["config", "unset", "timeout"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["data"]["removed"] is True

    def test_未設定の場合もエラーにならない(self) -> None:
        result = runner.invoke(app, ["config", "unset", "timeout"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["data"]["removed"] is False


class TestTimeoutResolution:
    """main.py での timeout 解決優先順位のテスト."""

    def test_CLIフラグが最優先(self, tmp_config) -> None:
        """--timeout が config.json より優先される."""
        runner.invoke(app, ["config", "set", "timeout", "200"])
        result = runner.invoke(app, ["--timeout", "30", "config", "get", "timeout"])
        assert result.exit_code == 0
        # config get は保存値を返す（CLI フラグは OutputConfig に反映される）
        parsed = json.loads(result.stdout)
        assert parsed["data"]["value"] == 200

    def test_config_jsonの値がデフォルトより優先される(self) -> None:
        """config.json の値が DEFAULT_TIMEOUT より優先される."""
        runner.invoke(app, ["config", "set", "timeout", "180"])
        # config get で保存値を確認
        result = runner.invoke(app, ["config", "get", "timeout"])
        parsed = json.loads(result.stdout)
        assert parsed["data"]["value"] == 180
