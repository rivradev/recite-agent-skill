import json
import os
import pytest

import process_receipts
from recite_client import ReciteError


class TestGetApiKey:
    def test_reads_from_config_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"api_key": "re_live_test123"}', encoding="utf-8")
        monkeypatch.setattr(process_receipts, "CONFIG_PATH", str(config_file))
        monkeypatch.delenv("RECITE_API_KEY", raising=False)
        assert process_receipts.get_api_key() == "re_live_test123"

    def test_config_file_exists_no_api_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"other_key": "value"}', encoding="utf-8")
        monkeypatch.setattr(process_receipts, "CONFIG_PATH", str(config_file))
        monkeypatch.setenv("RECITE_API_KEY", "env_key")
        assert process_receipts.get_api_key() == "env_key"

    def test_config_file_broken_json(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("{broken json", encoding="utf-8")
        monkeypatch.setattr(process_receipts, "CONFIG_PATH", str(config_file))
        monkeypatch.setenv("RECITE_API_KEY", "env_key")
        assert process_receipts.get_api_key() == "env_key"

    def test_no_config_file_reads_env(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            process_receipts, "CONFIG_PATH", str(tmp_path / "nonexistent.json")
        )
        monkeypatch.setenv("RECITE_API_KEY", "env_key")
        assert process_receipts.get_api_key() == "env_key"


class TestRequireApiKey:
    def test_key_found(self, monkeypatch):
        monkeypatch.setattr(process_receipts, "get_api_key", lambda: "key123")
        assert process_receipts.require_api_key() == "key123"

    def test_key_not_found_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(process_receipts, "get_api_key", lambda: None)
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.require_api_key()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "API key not found" in out


class TestOutputFailure:
    def test_with_http_status(self, capsys):
        process_receipts.output_failure("CODE", "msg", http_status=400)
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error"]["code"] == "CODE"
        assert payload["http_status"] == 400

    def test_without_http_status(self, capsys):
        process_receipts.output_failure("CODE", "msg")
        payload = json.loads(capsys.readouterr().out)
        assert "http_status" not in payload


class TestOutputError:
    def test_converts_recite_error(self, capsys):
        err = ReciteError("ERR_CODE", "err msg", status=422)
        process_receipts.output_error(err)
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error"]["code"] == "ERR_CODE"
        assert payload["http_status"] == 422


class TestMainDispatch:
    def test_no_args_prints_help(self, monkeypatch, capsys):
        monkeypatch.setattr(process_receipts.sys, "argv", ["process_receipts.py"])
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()
        assert exc_info.value.code == 0

    def test_backward_compat_bare_directory(self, monkeypatch):
        monkeypatch.setattr(process_receipts, "require_api_key", lambda: "key")
        monkeypatch.setattr(
            process_receipts,
            "ReciteClient",
            lambda api_key: type(
                "FC",
                (),
                {
                    "scan_file": lambda *a, **kw: {
                        "data": {
                            "extracted_data": {"date": "2024-01-01", "vendor": "X"},
                            "scan_id": "s1",
                            "transaction_type": "expense",
                        },
                        "meta": {},
                    }
                },
            )(),
        )
        monkeypatch.setattr(
            process_receipts.sys, "argv", ["process_receipts.py", "some_dir"]
        )
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()
        assert process_receipts.sys.argv[1] == "scan-dir"

    def test_recite_error_dispatch(self, monkeypatch, capsys):
        class FakeClient:
            def __init__(self, api_key):
                pass

            def get_usage(self):
                raise ReciteError("API_ERROR", "bad request", status=400)

        monkeypatch.setattr(process_receipts, "require_api_key", lambda: "key")
        monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
        monkeypatch.setattr(
            process_receipts.sys, "argv", ["process_receipts.py", "usage"]
        )
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()
        assert exc_info.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"]["code"] == "API_ERROR"

    def test_value_error_dispatch(self, monkeypatch, capsys):
        class FakeClient:
            def __init__(self, api_key):
                pass

            def get_usage(self):
                raise ValueError("bad input")

        monkeypatch.setattr(process_receipts, "require_api_key", lambda: "key")
        monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
        monkeypatch.setattr(
            process_receipts.sys, "argv", ["process_receipts.py", "usage"]
        )
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()
        assert exc_info.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"]["code"] == "INVALID_INPUT"

    def test_file_not_found_dispatch(self, monkeypatch, capsys):
        class FakeClient:
            def __init__(self, api_key):
                pass

            def scan_file(self, *a, **kw):
                e = FileNotFoundError()
                e.filename = "missing.jpg"
                raise e

        monkeypatch.setattr(process_receipts, "require_api_key", lambda: "key")
        monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
        monkeypatch.setattr(
            process_receipts.sys, "argv", ["process_receipts.py", "scan", "missing.jpg"]
        )
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "missing.jpg" in out

    def test_keyboard_interrupt(self, monkeypatch, capsys):
        class FakeClient:
            def __init__(self, api_key):
                pass

            def get_usage(self):
                raise KeyboardInterrupt()

        monkeypatch.setattr(process_receipts, "require_api_key", lambda: "key")
        monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
        monkeypatch.setattr(
            process_receipts.sys, "argv", ["process_receipts.py", "usage"]
        )
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()
        assert exc_info.value.code == 130
