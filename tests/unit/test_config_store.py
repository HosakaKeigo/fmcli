"""config_store のテスト."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fmcli.infra.config_store import (
    config_get,
    config_get_effective,
    config_list,
    config_set,
    config_unset,
)


@pytest.fixture()
def tmp_config(tmp_path):
    """テスト用の一時設定ファイル."""
    config_file = tmp_path / "config.json"
    with patch("fmcli.infra.config_store._config_path", return_value=config_file):
        yield config_file


class TestConfigSet:
    def test_timeout_を設定できる(self, tmp_config) -> None:
        result = config_set("timeout", "120")
        assert result == 120
        assert tmp_config.exists()

    def test_timeout_を上書きできる(self, tmp_config) -> None:
        config_set("timeout", "60")
        config_set("timeout", "300")
        assert config_get("timeout") == 300

    def test_不正なキーでエラー(self, tmp_config) -> None:
        with pytest.raises(ValueError, match="不明な設定キー"):
            config_set("unknown_key", "value")

    def test_timeout_に文字列を渡すとエラー(self, tmp_config) -> None:
        with pytest.raises(ValueError, match="正の整数"):
            config_set("timeout", "abc")

    def test_timeout_に0を渡すとエラー(self, tmp_config) -> None:
        with pytest.raises(ValueError, match="1 以上"):
            config_set("timeout", "0")

    def test_timeout_に負数を渡すとエラー(self, tmp_config) -> None:
        with pytest.raises(ValueError, match="1 以上"):
            config_set("timeout", "-5")


class TestConfigGet:
    def test_設定済みの値を取得できる(self, tmp_config) -> None:
        config_set("timeout", "90")
        assert config_get("timeout") == 90

    def test_未設定の場合Noneを返す(self, tmp_config) -> None:
        assert config_get("timeout") is None

    def test_不正なキーでエラー(self, tmp_config) -> None:
        with pytest.raises(ValueError, match="不明な設定キー"):
            config_get("unknown_key")


class TestConfigList:
    def test_空の場合は空dictを返す(self, tmp_config) -> None:
        assert config_list() == {}

    def test_設定済みの値を返す(self, tmp_config) -> None:
        config_set("timeout", "120")
        result = config_list()
        assert result == {"timeout": 120}


class TestConfigUnset:
    def test_設定を削除できる(self, tmp_config) -> None:
        config_set("timeout", "120")
        assert config_unset("timeout") is True
        assert config_get("timeout") is None

    def test_未設定の場合Falseを返す(self, tmp_config) -> None:
        assert config_unset("timeout") is False

    def test_不正なキーでエラー(self, tmp_config) -> None:
        with pytest.raises(ValueError, match="不明な設定キー"):
            config_unset("unknown_key")


class TestConfigFileCorruption:
    def test_壊れたJSONは空dictとして扱う(self, tmp_config) -> None:
        tmp_config.write_text("{ invalid json", encoding="utf-8")
        assert config_list() == {}

    def test_壊れたJSON上に新しい値を書ける(self, tmp_config) -> None:
        tmp_config.write_text("{ invalid json", encoding="utf-8")
        config_set("timeout", "30")
        assert config_get("timeout") == 30

    def test_配列JSONは空dictとして扱う(self, tmp_config) -> None:
        tmp_config.write_text("[1, 2, 3]", encoding="utf-8")
        assert config_list() == {}

    def test_文字列JSONは空dictとして扱う(self, tmp_config) -> None:
        tmp_config.write_text('"hello"', encoding="utf-8")
        assert config_list() == {}

    def test_手編集でboolが入った場合Noneを返す(self, tmp_config) -> None:
        tmp_config.write_text('{"timeout": true}', encoding="utf-8")
        assert config_get("timeout") is None

    def test_手編集で0が入った場合Noneを返す(self, tmp_config) -> None:
        tmp_config.write_text('{"timeout": 0}', encoding="utf-8")
        assert config_get("timeout") is None

    def test_手編集で負数が入った場合Noneを返す(self, tmp_config) -> None:
        tmp_config.write_text('{"timeout": -5}', encoding="utf-8")
        assert config_get("timeout") is None

    def test_手編集で文字列が入った場合Noneを返す(self, tmp_config) -> None:
        tmp_config.write_text('{"timeout": "abc"}', encoding="utf-8")
        assert config_get("timeout") is None


class TestConfigGetEffective:
    def test_設定済みの値を返す(self, tmp_config) -> None:
        config_set("timeout", "90")
        assert config_get_effective("timeout") == 90

    def test_未設定の場合デフォルト値を返す(self, tmp_config) -> None:
        assert config_get_effective("timeout") == 60

    def test_不正値の場合デフォルト値を返す(self, tmp_config) -> None:
        tmp_config.write_text('{"timeout": true}', encoding="utf-8")
        assert config_get_effective("timeout") == 60
