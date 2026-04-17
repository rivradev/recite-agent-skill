import argparse
import csv
import os
import json
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest

import process_receipts
from recite_client import ReciteError
from tests.conftest import _case_dir


TEST_TMP_DIR = Path(os.getcwd()) / ".test_tmp"


class FakeReciteClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def scan_file(
        self,
        file_path,
        project_id=None,
        format=None,
        auto_create_transaction=None,
        confidence_threshold=None,
    ):
        self.calls.append((file_path, project_id))
        return self.result


def _scan_dir_args(directory, **overrides):
    defaults = dict(
        directory=str(directory),
        skill_path=str(directory),
        project_id=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _read_csv_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_scan_dir_skips_files_already_recorded_as_new_filename():
    with _case_dir("skip_recorded") as tmp_path:
        receipt_path = tmp_path / "2024-05-20_Store.jpg"
        receipt_path.write_bytes(b"receipt-bytes")

        csv_path = tmp_path / process_receipts.CSV_NAME
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["OriginalFilename", "NewFilename", "scan_id"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "OriginalFilename": "IMG_0001.jpg",
                    "NewFilename": receipt_path.name,
                    "scan_id": "scan-existing",
                }
            )

        client = FakeReciteClient(
            {
                "data": {
                    "extracted_data": {"date": "2024-05-20", "vendor": "Store"},
                    "scan_id": "scan-new",
                    "transaction_type": "expense",
                },
                "meta": {"quota_remaining": 9},
            }
        )

        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)

        assert client.calls == []
        assert receipt_path.exists()
        assert _read_csv_rows(csv_path) == [
            {
                "OriginalFilename": "IMG_0001.jpg",
                "NewFilename": receipt_path.name,
                "scan_id": "scan-existing",
            }
        ]


def test_scan_dir_processes_new_file_and_appends_ledger_row():
    with _case_dir("process_new") as tmp_path:
        receipt_path = tmp_path / "receipt.jpg"
        receipt_path.write_bytes(b"receipt-bytes")

        client = FakeReciteClient(
            {
                "data": {
                    "extracted_data": {
                        "date": "2024-05-20",
                        "vendor": "Store",
                        "total": 12.34,
                    },
                    "scan_id": "scan-1",
                    "transaction_type": "expense",
                },
                "meta": {"quota_remaining": 19},
            }
        )

        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)

        renamed_path = tmp_path / "2024-05-20_Store.jpg"
        csv_path = tmp_path / process_receipts.CSV_NAME

        assert client.calls == [(str(receipt_path), None)]
        assert renamed_path.exists()

        rows = _read_csv_rows(csv_path)
        assert len(rows) == 1
        assert rows[0]["OriginalFilename"] == "receipt.jpg"
        assert rows[0]["NewFilename"] == "2024-05-20_Store.jpg"
        assert rows[0]["scan_id"] == "scan-1"
        assert rows[0]["transaction_type"] == "expense"
        assert rows[0]["date"] == "2024-05-20"
        assert rows[0]["vendor"] == "Store"
        assert rows[0]["total"] == "12.34"


def test_scan_dir_not_a_directory():
    with _case_dir("not_dir") as tmp_path:
        fake_file = tmp_path / "notafile.jpg"
        fake_file.write_bytes(b"data")
        client = FakeReciteClient({})
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.cmd_scan_dir(_scan_dir_args(str(fake_file)), client)
        assert exc_info.value.code == 1


def test_scan_dir_no_receipt_files(capsys):
    with _case_dir("empty_dir") as tmp_path:
        client = FakeReciteClient({})
        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)
        assert client.calls == []
        out = capsys.readouterr().out
        assert "No receipt files" in out


def test_scan_dir_skips_csv_ledger(capsys):
    with _case_dir("skip_csv") as tmp_path:
        csv_file = tmp_path / process_receipts.CSV_NAME
        csv_file.write_text("header\n", encoding="utf-8")
        receipt = tmp_path / "receipt.jpg"
        receipt.write_bytes(b"data")
        client = FakeReciteClient(
            {
                "data": {
                    "extracted_data": {"date": "2024-01-01", "vendor": "V"},
                    "scan_id": "s1",
                    "transaction_type": "expense",
                },
                "meta": {},
            }
        )
        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)
        assert len(client.calls) == 1


def test_scan_dir_recite_error(capsys):
    class ErrorClient:
        def scan_file(self, *a, **kw):
            raise ReciteError("SCAN_FAIL", "API error")

    with _case_dir("scan_error") as tmp_path:
        receipt = tmp_path / "receipt.jpg"
        receipt.write_bytes(b"data")
        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), ErrorClient())
        out = capsys.readouterr().out
        assert "SCAN_FAIL" in out
        assert "Errors" in out


def test_scan_dir_rename_falls_back(monkeypatch, capsys):
    with _case_dir("rename_fail") as tmp_path:
        receipt = tmp_path / "receipt.jpg"
        receipt.write_bytes(b"data")

        orig_rename = os.rename

        def bad_rename(src, dst):
            if "2024-05-20_Store" in dst:
                raise OSError("permission denied")
            return orig_rename(src, dst)

        monkeypatch.setattr("os.rename", bad_rename)
        client = FakeReciteClient(
            {
                "data": {
                    "extracted_data": {"date": "2024-05-20", "vendor": "Store"},
                    "scan_id": "s1",
                    "transaction_type": "expense",
                },
                "meta": {},
            }
        )
        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)
        out = capsys.readouterr().out
        assert "Warning" in out
        csv_path = tmp_path / process_receipts.CSV_NAME
        rows = _read_csv_rows(csv_path)
        assert rows[0]["NewFilename"] == "receipt.jpg"


def test_scan_dir_prints_ltm(capsys):
    with _case_dir("ltm_test") as tmp_path:
        ltm = tmp_path / "long_term_memory.md"
        ltm.write_text("# My Rules\n- Always categorize coffee", encoding="utf-8")
        receipt = tmp_path / "receipt.jpg"
        receipt.write_bytes(b"data")
        client = FakeReciteClient(
            {
                "data": {
                    "extracted_data": {"date": "2024-01-01", "vendor": "V"},
                    "scan_id": "s1",
                    "transaction_type": "expense",
                },
                "meta": {},
            }
        )
        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)
        out = capsys.readouterr().out
        assert "Long-Term Memory" in out


def test_read_ltm_file_not_exists():
    assert process_receipts.read_ltm("/nonexistent/path") == ""


def test_get_processed_filenames_broken_csv(tmp_path):
    bad_csv = tmp_path / "bad.CSV"
    bad_csv.write_bytes(b"\xff\xfe\x00\x00bad binary content")
    result = process_receipts.get_processed_filenames(str(bad_csv))
    assert result == set()


def test_get_processed_filenames_returns_filenames(tmp_path):
    csv_path = tmp_path / "test.CSV"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["OriginalFilename", "NewFilename"])
        writer.writeheader()
        writer.writerow({"OriginalFilename": "a.jpg", "NewFilename": "b.jpg"})
    result = process_receipts.get_processed_filenames(str(csv_path))
    assert result == {"a.jpg", "b.jpg"}


def test_flatten_dict_nested():
    result = process_receipts.flatten_dict({"a": {"b": 1, "c": {"d": 2}}})
    assert result == {"a_b": 1, "a_c_d": 2}


def test_flatten_dict_list_value():
    result = process_receipts.flatten_dict({"tags": ["a", "b"]})
    assert result == {"tags": '["a", "b"]'}


def test_update_csv_new_columns(tmp_path):
    csv_path = tmp_path / "test.CSV"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["a", "b"])
        writer.writeheader()
        writer.writerow({"a": "1", "b": "2"})
    process_receipts.update_csv(str(csv_path), {"a": "3", "b": "4", "c": "5"})
    rows = _read_csv_rows(str(csv_path))
    assert len(rows) == 2
    assert rows[0]["c"] == ""
    assert rows[1]["c"] == "5"


def test_update_csv_new_file_append(tmp_path):
    csv_path = tmp_path / "new.CSV"
    assert not os.path.exists(csv_path)
    process_receipts.update_csv(str(csv_path), {"date": "2024-01-01", "vendor": "S"})
    assert os.path.exists(csv_path)
    rows = _read_csv_rows(str(csv_path))
    assert len(rows) == 1
    assert rows[0]["date"] == "2024-01-01"
    assert rows[0]["vendor"] == "S"


def test_update_csv_existing_file_no_new_columns(tmp_path):
    csv_path = tmp_path / "test.CSV"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["a", "b"])
        writer.writeheader()
        writer.writerow({"a": "1", "b": "2"})
    process_receipts.update_csv(str(csv_path), {"a": "3", "b": "4"})
    rows = _read_csv_rows(str(csv_path))
    assert len(rows) == 2
    assert rows[1]["a"] == "3"


def test_update_csv_atomic_rewrite_failure(tmp_path, monkeypatch):
    csv_path = tmp_path / "test.CSV"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["a"])
        writer.writeheader()
        writer.writerow({"a": "1"})
    real_replace = os.replace

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        process_receipts.update_csv(str(csv_path), {"a": "2", "new_col": "x"})


def test_unique_filename_collision(tmp_path, monkeypatch):
    existing = tmp_path / "2024-05-20_Store.jpg"
    existing.write_bytes(b"data")
    monkeypatch.setattr("time.time", lambda: 1700000000)
    result = process_receipts.unique_filename(
        str(tmp_path), "2024-05-20", "Store", ".jpg"
    )
    assert "1700000000" in result
    assert result.startswith("2024-05-20_Store_")


def test_unique_filename_counter_increments(tmp_path, monkeypatch):
    base = tmp_path / "2024-05-20_Store.jpg"
    base.write_bytes(b"data")
    ts = 1700000000
    ts_file = tmp_path / f"2024-05-20_Store_{ts}.jpg"
    ts_file.write_bytes(b"data")
    monkeypatch.setattr("time.time", lambda: ts)
    result = process_receipts.unique_filename(
        str(tmp_path), "2024-05-20", "Store", ".jpg"
    )
    assert result == f"2024-05-20_Store_{ts}_1.jpg"


def test_update_csv_no_new_fields_new_file(tmp_path):
    csv_path = tmp_path / "empty.CSV"
    process_receipts.update_csv(str(csv_path), {"date": "2024-01-01", "vendor": "S"})
    assert csv_path.exists()
    rows = _read_csv_rows(str(csv_path))
    assert len(rows) == 1
    assert rows[0]["date"] == "2024-01-01"


def test_update_csv_empty_row_new_file(tmp_path):
    csv_path = tmp_path / "empty_new.CSV"
    process_receipts.update_csv(str(csv_path), {})
    assert csv_path.exists()
    with open(csv_path, newline="", encoding="utf-8") as f:
        content = f.read()
    assert content.strip() == ""


def test_scan_dir_skips_file_with_csv_name_in_basename(capsys):
    with _case_dir("csv_name_file") as tmp_path:
        tricky = tmp_path / f"{process_receipts.CSV_NAME}_notes.jpg"
        tricky.write_bytes(b"data")
        receipt = tmp_path / "receipt.jpg"
        receipt.write_bytes(b"data")
        client = FakeReciteClient(
            {
                "data": {
                    "extracted_data": {"date": "2024-01-01", "vendor": "V"},
                    "scan_id": "s1",
                    "transaction_type": "expense",
                },
                "meta": {},
            }
        )
        process_receipts.cmd_scan_dir(_scan_dir_args(tmp_path), client)
        assert len(client.calls) == 1
        assert client.calls[0][0] == str(receipt)


def test_get_receipt_files_case_insensitive(tmp_path):
    lower = tmp_path / "photo.jpg"
    lower.write_bytes(b"data")
    upper = tmp_path / "photo.JPG"
    upper.write_bytes(b"data")
    files = process_receipts.get_receipt_files(str(tmp_path))
    basenames = [os.path.basename(f) for f in files]
    assert len(basenames) == len(set(os.path.normcase(n) for n in basenames))
