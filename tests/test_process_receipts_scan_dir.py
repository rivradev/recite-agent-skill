import argparse
import csv
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import process_receipts


TEST_TMP_DIR = Path(os.getcwd()) / ".test_tmp"


class FakeReciteClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def scan_file(self, file_path, project_id=None, format=None, auto_create_transaction=None, confidence_threshold=None):
        self.calls.append((file_path, project_id))
        return self.result


def _scan_dir_args(directory):
    return argparse.Namespace(
        directory=str(directory),
        skill_path=str(directory),
        project_id=None,
    )


def _read_csv_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
