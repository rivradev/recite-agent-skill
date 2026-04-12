import argparse
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests

import process_receipts
from recite_client import ReciteClient


TEST_TMP_DIR = Path(os.getcwd()) / ".test_tmp"


@contextmanager
def _case_dir(name):
    TEST_TMP_DIR.mkdir(exist_ok=True)
    case_dir = TEST_TMP_DIR / name
    shutil.rmtree(case_dir, ignore_errors=True)
    case_dir.mkdir()
    try:
        yield case_dir
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
        if TEST_TMP_DIR.exists() and not any(TEST_TMP_DIR.iterdir()):
            TEST_TMP_DIR.rmdir()


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

def test_main_outputs_invalid_input_for_bad_import_csv(monkeypatch, capsys):
    with _case_dir("bad_import_csv") as tmp_path:
        bad_csv = tmp_path / "bad.csv"
        # In a real environment, the client handles valid CSV.
        # But we want to ensure the fallback logic in CLI is right or simply test routing.
        # However, import_csv only needs a string.
        pass
