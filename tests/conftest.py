import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from recite_client import ReciteClient


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")


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


@pytest.fixture
def tmp_case_dir():
    with _case_dir("fixture_case") as d:
        yield d


@pytest.fixture
def fake_client():
    client = MagicMock(spec=ReciteClient)
    client.scan_file.return_value = {
        "success": True,
        "data": {
            "extracted_data": {"date": "2024-05-20", "vendor": "Store", "total": 12.34},
            "scan_id": "scan-1",
            "transaction_type": "expense",
        },
        "meta": {"quota_remaining": 19},
    }
    client.scan_url.return_value = {"success": True, "data": {}}
    client.scan_text.return_value = {"success": True, "data": {}}
    client.get_scan.return_value = {"success": True, "data": {}}
    client.create_batch.return_value = {"success": True, "data": {}}
    client.get_batch_status.return_value = {"success": True, "data": {}}
    client.get_batch_results.return_value = {"success": True, "data": []}
    client.list_transactions.return_value = {"success": True, "data": []}
    client.get_transaction.return_value = {"success": True, "data": {}}
    client.create_transaction.return_value = {"success": True, "data": {}}
    client.update_transaction.return_value = {"success": True}
    client.delete_transaction.return_value = {"success": True}
    client.import_transactions.return_value = {"success": True}
    client.import_csv.return_value = {"success": True}
    client.list_projects.return_value = {"success": True, "data": []}
    client.create_project.return_value = {"success": True, "data": {}}
    client.update_project.return_value = {"success": True}
    client.delete_project.return_value = {"success": True}
    client.get_summary.return_value = {"success": True, "data": {}}
    client.list_webhooks.return_value = {"success": True, "data": []}
    client.create_webhook.return_value = {"success": True, "data": {}}
    client.delete_webhook.return_value = {"success": True}
    client.list_rules.return_value = {"success": True, "data": []}
    client.create_rule.return_value = {"success": True, "data": {}}
    client.update_rule.return_value = {"success": True}
    client.delete_rule.return_value = {"success": True}
    client.list_categories.return_value = {"success": True, "data": []}
    client.create_category.return_value = {"success": True, "data": {}}
    client.delete_category.return_value = {"success": True}
    client.list_vendors.return_value = {"success": True, "data": []}
    client.create_vendor.return_value = {"success": True, "data": {}}
    client.delete_vendor.return_value = {"success": True}
    client.export_transactions.return_value = {"success": True, "data": {}}
    client.get_usage.return_value = {"success": True, "data": {}}
    client.list_bank_statements.return_value = {"success": True, "data": []}
    client.get_bank_statement.return_value = {"success": True, "data": {}}
    client.delete_bank_statement.return_value = {"success": True}
    client.export_bank_statement.return_value = {"success": True, "data": {}}
    client.upload_bank_statement.return_value = {"success": True, "data": {}}
    client.list_bank_transactions.return_value = {"success": True, "data": []}
    client.get_bank_transaction.return_value = {"success": True, "data": {}}
    client.update_bank_transaction.return_value = {"success": True}
    client.delete_bank_transaction.return_value = {"success": True}
    client.create_reconciliation_link.return_value = {"success": True, "data": {}}
    client.list_reconciliation_links.return_value = {"success": True, "data": []}
    client.update_reconciliation_link.return_value = {"success": True}
    client.delete_reconciliation_link.return_value = {"success": True}
    client.auto_match_reconciliation.return_value = {"success": True, "data": {}}
    client.get_reconciliation_summary.return_value = {"success": True, "data": {}}
    client.export_reconciliation.return_value = {"success": True, "data": {}}
    return client
