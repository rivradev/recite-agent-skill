import json

import pytest
import requests

import process_receipts
from recite_client import ReciteClient
from tests.conftest import _case_dir


class FakeClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_usage(self):
        raise requests.RequestException("network down")

    def import_transactions(self, transactions):
        raise AssertionError("import_transactions should not be called")

    def create_transaction(self, **kwargs):
        raise AssertionError("create_transaction should not be called")


def test_parse_kv_list_rejects_tokens_without_equals():
    with pytest.raises(ValueError, match="key=value"):
        process_receipts._parse_kv_list(["notes"])


def test_parse_kv_list_rejects_empty_keys():
    with pytest.raises(ValueError, match="empty key"):
        process_receipts._parse_kv_list(["=value"])


def test_main_outputs_invalid_input_for_bad_total(monkeypatch, capsys):
    monkeypatch.setattr(process_receipts, "require_api_key", lambda: "test-key")
    monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
    monkeypatch.setattr(
        process_receipts.sys,
        "argv",
        [
            "process_receipts.py",
            "transaction-create",
            "--vendor",
            "Store",
            "--total",
            "oops",
            "--date",
            "2024-05-20",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        process_receipts.main()

    assert exc_info.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
    assert "total" in payload["error"]["message"].lower()


def test_main_outputs_invalid_input_for_bad_import_json(monkeypatch, capsys):
    with _case_dir("bad_import_json") as tmp_path:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{not valid json", encoding="utf-8")

        monkeypatch.setattr(process_receipts, "require_api_key", lambda: "test-key")
        monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
        monkeypatch.setattr(
            process_receipts.sys,
            "argv",
            ["process_receipts.py", "import", str(bad_json)],
        )

        with pytest.raises(SystemExit) as exc_info:
            process_receipts.main()

        assert exc_info.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error"]["code"] == "INVALID_INPUT"
        assert "json" in payload["error"]["message"].lower()


def test_main_outputs_request_failed_for_request_exceptions(monkeypatch, capsys):
    monkeypatch.setattr(process_receipts, "require_api_key", lambda: "test-key")
    monkeypatch.setattr(process_receipts, "ReciteClient", FakeClient)
    monkeypatch.setattr(process_receipts.sys, "argv", ["process_receipts.py", "usage"])

    with pytest.raises(SystemExit) as exc_info:
        process_receipts.main()

    assert exc_info.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error"]["code"] == "REQUEST_FAILED"
    assert "network down" in payload["error"]["message"].lower()


def test_encode_file_rejects_unsupported_extensions():
    with _case_dir("unsupported_extension") as tmp_path:
        bad_file = tmp_path / "receipt.txt"
        bad_file.write_text("not a receipt image", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            ReciteClient._encode_file(str(bad_file))


def test_parse_kv_list_float_value():
    result = process_receipts._parse_kv_list(["total=12.34"])
    assert result == {"total": 12.34}


def test_parse_kv_list_negative_int():
    result = process_receipts._parse_kv_list(["amount=-5"])
    assert result == {"amount": -5}


def test_parse_kv_list_true_boolean():
    result = process_receipts._parse_kv_list(["enabled=true"])
    assert result == {"enabled": True}


def test_parse_kv_list_false_boolean():
    result = process_receipts._parse_kv_list(["enabled=false"])
    assert result == {"enabled": False}


def test_parse_kv_list_mixed_types():
    result = process_receipts._parse_kv_list(
        ["name=test", "count=42", "rate=3.14", "active=true", "disabled=false"]
    )
    assert result == {
        "name": "test",
        "count": 42,
        "rate": 3.14,
        "active": True,
        "disabled": False,
    }
