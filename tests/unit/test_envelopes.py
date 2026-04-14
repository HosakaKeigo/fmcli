"""Envelope モデルのテスト."""

from __future__ import annotations

from fmcli.domain.envelopes import ApiInfo, Envelope, ErrorDetail
from fmcli.domain.models import Pagination, Profile


class TestErrorDetail:
    """ErrorDetail の構築とシリアライズ."""

    def test_minimal_construction(self) -> None:
        """message のみで構築できる."""
        d = ErrorDetail(message="something went wrong")
        assert d.message == "something went wrong"
        assert d.type is None
        assert d.http_status is None
        assert d.api_code is None
        assert d.retryable is False
        assert d.hint == ""
        assert d.host == ""
        assert d.database == ""

    def test_full_construction(self) -> None:
        d = ErrorDetail(
            type="auth_expired",
            message="Session expired",
            http_status=401,
            api_code=952,
            retryable=True,
            hint="Re-login",
            host="https://fm.example.com",
            database="MyDB",
        )
        assert d.type == "auth_expired"
        assert d.http_status == 401
        assert d.api_code == 952
        assert d.retryable is True
        assert d.host == "https://fm.example.com"

    def test_model_dump(self) -> None:
        """model_dump で辞書に変換できる."""
        d = ErrorDetail(message="err", http_status=500)
        dumped = d.model_dump()
        assert dumped["message"] == "err"
        assert dumped["http_status"] == 500
        assert dumped["retryable"] is False

    def test_model_dump_exclude_none(self) -> None:
        """exclude_none で None フィールドを除外できる."""
        d = ErrorDetail(message="err")
        dumped = d.model_dump(exclude_none=True)
        assert "type" not in dumped
        assert "http_status" not in dumped
        assert "api_code" not in dumped
        # デフォルト値のあるフィールドは残る
        assert "message" in dumped
        assert "retryable" in dumped


class TestApiInfo:
    def test_defaults(self) -> None:
        info = ApiInfo()
        assert info.method == ""
        assert info.url == ""
        assert info.duration_ms is None

    def test_with_values(self) -> None:
        info = ApiInfo(method="POST", url="https://fm.example.com/fmi/data", duration_ms=123.4)
        assert info.method == "POST"
        assert info.duration_ms == 123.4


class TestEnvelopeFactoryMethods:
    """Envelope のファクトリメソッド."""

    def test_from_profile_basic(self) -> None:
        """from_profile で profile 情報が引き継がれる."""
        p = Profile(name="dev", host="https://fm.example.com", database="TestDB")
        env = Envelope.from_profile(p, command="record get")
        assert env.ok is True
        assert env.command == "record get"
        assert env.profile == "https://fm.example.com|TestDB"
        assert env.database == "TestDB"

    def test_from_profile_with_data(self) -> None:
        """from_profile で追加の kwargs が渡せる."""
        p = Profile(name="dev", host="https://fm.example.com", database="TestDB")
        env = Envelope.from_profile(
            p,
            command="record list",
            data=[{"id": 1}],
            layout="Users",
        )
        assert env.data == [{"id": 1}]
        assert env.layout == "Users"

    def test_from_profile_with_pagination(self) -> None:
        pag = Pagination(offset=1, limit=10, total_count=100, found_count=50, returned_count=10)
        p = Profile(name="dev", host="https://fm.example.com", database="TestDB")
        env = Envelope.from_profile(p, command="record list", pagination=pag)
        assert env.pagination is not None
        assert env.pagination.total_count == 100

    def test_from_profile_without_database(self) -> None:
        """database が空の profile でも動作する."""
        p = Profile(name="dev", host="https://fm.example.com")
        env = Envelope.from_profile(p, command="host info")
        assert env.profile == "https://fm.example.com"
        assert env.database == ""

    def test_from_profile_with_trailing_slash(self) -> None:
        """host に末尾スラッシュがあっても profile_key では除去される."""
        p = Profile(name="dev", host="https://fm.example.com/", database="DB")
        env = Envelope.from_profile(p, command="test")
        assert env.profile == "https://fm.example.com|DB"


class TestEnvelopeModelDump:
    """Envelope の model_dump 出力形式."""

    def test_success_envelope_dump(self) -> None:
        env = Envelope(ok=True, command="test", data={"key": "value"})
        dumped = env.model_dump()
        assert dumped["ok"] is True
        assert dumped["command"] == "test"
        assert dumped["data"] == {"key": "value"}
        assert dumped["error"] is None
        assert dumped["messages"] == []

    def test_error_envelope_dump(self) -> None:
        env = Envelope(
            ok=False,
            command="record get",
            error=ErrorDetail(message="Not found", http_status=404),
        )
        dumped = env.model_dump()
        assert dumped["ok"] is False
        assert dumped["error"]["message"] == "Not found"
        assert dumped["error"]["http_status"] == 404

    def test_exclude_none_removes_optional_fields(self) -> None:
        env = Envelope(ok=True, command="test", data="hello")
        dumped = env.model_dump(exclude_none=True)
        assert "pagination" not in dumped
        assert "api" not in dumped
        assert "script_results" not in dumped
        assert "error" not in dumped

    def test_json_serialization_roundtrip(self) -> None:
        """JSON シリアライズ→デシリアライズで値が保持される."""
        env = Envelope(
            ok=True,
            command="record find",
            data=[1, 2, 3],
            messages=["Found 3 records"],
        )
        json_str = env.model_dump_json()
        restored = Envelope.model_validate_json(json_str)
        assert restored.ok is True
        assert restored.data == [1, 2, 3]
        assert restored.messages == ["Found 3 records"]

    def test_various_data_types(self) -> None:
        """data フィールドに様々な型を格納できる."""
        # None
        assert Envelope(data=None).data is None
        # 文字列
        assert Envelope(data="hello").data == "hello"
        # リスト
        assert Envelope(data=[1, 2]).data == [1, 2]
        # 辞書
        assert Envelope(data={"a": 1}).data == {"a": 1}
        # ネストした構造
        assert Envelope(data={"nested": [{"x": 1}]}).data == {"nested": [{"x": 1}]}
        # 数値
        assert Envelope(data=42).data == 42
        # 真偽値
        assert Envelope(data=True).data is True

    def test_messages_list(self) -> None:
        env = Envelope(messages=["msg1", "msg2"])
        assert len(env.messages) == 2

    def test_with_api_info(self) -> None:
        env = Envelope(
            ok=True,
            api=ApiInfo(method="GET", url="https://example.com", duration_ms=50.5),
        )
        dumped = env.model_dump()
        assert dumped["api"]["method"] == "GET"
        assert dumped["api"]["duration_ms"] == 50.5

    def test_with_script_results(self) -> None:
        env = Envelope(script_results={"prerequest": "ok", "presort": None})
        dumped = env.model_dump()
        assert dumped["script_results"]["prerequest"] == "ok"
