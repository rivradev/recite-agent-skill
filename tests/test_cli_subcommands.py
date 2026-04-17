import argparse
import json
import sys
import time

import pytest
from unittest.mock import MagicMock, patch

import process_receipts
from recite_client import ReciteClient


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


class TestCmdScan:
    def test_cmd_scan(self, fake_client, capsys):
        args = _ns(
            file="receipt.jpg",
            project_id=None,
            format=None,
            auto_create_transaction=None,
            confidence_threshold=None,
        )
        process_receipts.cmd_scan(args, fake_client)
        fake_client.scan_file.assert_called_once_with(
            "receipt.jpg",
            project_id=None,
            format=None,
            auto_create_transaction=None,
            confidence_threshold=None,
        )
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True


class TestCmdScanText:
    def test_scan_text_from_file(self, fake_client, capsys, tmp_path):
        f = tmp_path / "text.txt"
        f.write_text("receipt text content", encoding="utf-8")
        args = _ns(
            file=str(f),
            project_id=None,
            format=None,
            auto_create_transaction=None,
            confidence_threshold=None,
        )
        process_receipts.cmd_scan_text(args, fake_client)
        fake_client.scan_text.assert_called_once_with(
            "receipt text content",
            project_id=None,
            format=None,
            auto_create_transaction=None,
            confidence_threshold=None,
        )

    def test_scan_text_from_stdin(self, fake_client, capsys, monkeypatch):
        fake_stdin = MagicMock()
        fake_stdin.read.return_value = "stdin receipt text"
        monkeypatch.setattr(process_receipts.sys, "stdin", fake_stdin)
        args = _ns(
            file="-",
            project_id=None,
            format=None,
            auto_create_transaction=None,
            confidence_threshold=None,
        )
        process_receipts.cmd_scan_text(args, fake_client)
        fake_client.scan_text.assert_called_once_with(
            "stdin receipt text",
            project_id=None,
            format=None,
            auto_create_transaction=None,
            confidence_threshold=None,
        )


class TestCmdGetScan:
    def test_cmd_get_scan(self, fake_client, capsys):
        args = _ns(scan_id="scan123")
        process_receipts.cmd_get_scan(args, fake_client)
        fake_client.get_scan.assert_called_once_with("scan123")


class TestCmdBatch:
    def test_batch_warns_over_20(self, fake_client, capsys):
        files = [f"file{i}.jpg" for i in range(21)]
        args = _ns(files=files, project_id=None)
        process_receipts.cmd_batch(args, fake_client)
        err = capsys.readouterr().err
        assert "Warning" in err
        fake_client.create_batch.assert_called_once_with(files, project_id=None)

    def test_batch_status(self, fake_client, capsys):
        args = _ns(batch_id="bid")
        process_receipts.cmd_batch_status(args, fake_client)
        fake_client.get_batch_status.assert_called_once_with("bid")

    def test_batch_results(self, fake_client, capsys):
        args = _ns(batch_id="bid")
        process_receipts.cmd_batch_results(args, fake_client)
        fake_client.get_batch_results.assert_called_once_with("bid")


class TestCmdBatchWait:
    def test_completed_immediately(self, fake_client, capsys):
        fake_client.get_batch_status.return_value = {
            "success": True,
            "data": {"status": "completed"},
        }
        fake_client.get_batch_results.return_value = {
            "success": True,
            "data": [{"id": "r1"}],
        }
        args = _ns(batch_id="bid", timeout=60, interval=2)
        process_receipts.cmd_batch_wait(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True

    def test_failed_status(self, fake_client, capsys):
        fake_client.get_batch_status.return_value = {
            "success": True,
            "data": {"status": "failed"},
        }
        args = _ns(batch_id="bid", timeout=60, interval=2)
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.cmd_batch_wait(args, fake_client)
        assert exc_info.value.code == 1

    def test_timeout(self, fake_client, capsys, monkeypatch):
        fake_client.get_batch_status.return_value = {
            "success": True,
            "data": {"status": "processing"},
        }
        monkeypatch.setattr(time, "time", lambda: 0)
        monkeypatch.setattr(time, "sleep", lambda s: None)
        args = _ns(batch_id="bid", timeout=-1, interval=2)
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.cmd_batch_wait(args, fake_client)
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "timed out" in out.lower()

    def test_polls_twice_then_completes(self, fake_client, capsys, monkeypatch):
        call_count = {"n": 0}
        start_time = [100]

        def fake_time():
            return start_time[0]

        def fake_sleep(s):
            start_time[0] += s

        def fake_status(batch_id):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                return {"success": True, "data": {"status": "completed"}}
            return {"success": True, "data": {"status": "processing"}}

        fake_client.get_batch_status.side_effect = fake_status
        fake_client.get_batch_results.return_value = {"success": True, "data": []}

        monkeypatch.setattr(time, "time", fake_time)
        monkeypatch.setattr(time, "sleep", fake_sleep)
        args = _ns(batch_id="bid", timeout=300, interval=5)
        process_receipts.cmd_batch_wait(args, fake_client)
        assert call_count["n"] == 2


class TestCmdTransactions:
    def test_cmd_transactions(self, fake_client, capsys):
        args = _ns(
            start_date="2024-01-01",
            end_date="2024-12-31",
            category="Food",
            vendor="Store",
            project_id="p1",
            limit=10,
            offset=5,
            sort="-date",
        )
        process_receipts.cmd_transactions(args, fake_client)
        fake_client.list_transactions.assert_called_once_with(
            start_date="2024-01-01",
            end_date="2024-12-31",
            category="Food",
            vendor="Store",
            project_id="p1",
            limit=10,
            offset=5,
            sort="-date",
        )

    def test_cmd_transaction_get(self, fake_client, capsys):
        args = _ns(id="tx1")
        process_receipts.cmd_transaction_get(args, fake_client)
        fake_client.get_transaction.assert_called_once_with("tx1")

    def test_cmd_transaction_create_with_extra(self, fake_client, capsys):
        args = _ns(
            vendor="Store",
            total="10.50",
            date="2024-01-01",
            currency="USD",
            category=None,
            project_id=None,
            notes=None,
            extra=["source=mobile"],
        )
        process_receipts.cmd_transaction_create(args, fake_client)
        fake_client.create_transaction.assert_called_once_with(
            vendor="Store",
            total=10.50,
            date="2024-01-01",
            currency="USD",
            category=None,
            project_id=None,
            notes=None,
            source="mobile",
        )

    def test_cmd_transaction_update(self, fake_client, capsys):
        args = _ns(id="tx1", fields=["category=Travel", "notes=OK"])
        process_receipts.cmd_transaction_update(args, fake_client)
        fake_client.update_transaction.assert_called_once_with(
            "tx1", category="Travel", notes="OK"
        )

    def test_cmd_transaction_delete(self, fake_client, capsys):
        args = _ns(id="tx1")
        process_receipts.cmd_transaction_delete(args, fake_client)
        fake_client.delete_transaction.assert_called_once_with("tx1")


class TestCmdImport:
    def test_import_json_with_transactions_key(self, fake_client, capsys, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(
            '{"transactions": [{"vendor": "S", "total": 10}]}', encoding="utf-8"
        )
        args = _ns(file=str(f), format=None)
        process_receipts.cmd_import(args, fake_client)
        fake_client.import_transactions.assert_called_once_with(
            [{"vendor": "S", "total": 10}]
        )

    def test_import_json_not_list_no_transactions_key(self, fake_client, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        args = _ns(file=str(f), format=None)
        with pytest.raises(ValueError, match="list of transaction"):
            process_receipts.cmd_import(args, fake_client)


class TestCmdSummary:
    def test_cmd_summary(self, fake_client, capsys):
        args = _ns(
            start_date="2024-01-01",
            end_date="2024-12-31",
            group_by="category",
            project_id="p1",
        )
        process_receipts.cmd_summary(args, fake_client)
        fake_client.get_summary.assert_called_once_with(
            start_date="2024-01-01",
            end_date="2024-12-31",
            group_by="category",
            project_id="p1",
        )


class TestCmdProjects:
    def test_cmd_projects(self, fake_client, capsys):
        args = _ns()
        process_receipts.cmd_projects(args, fake_client)
        fake_client.list_projects.assert_called_once()

    def test_cmd_project_create(self, fake_client, capsys):
        args = _ns(name="Proj", description="desc")
        process_receipts.cmd_project_create(args, fake_client)
        fake_client.create_project.assert_called_once_with("Proj", description="desc")

    def test_cmd_project_update(self, fake_client, capsys):
        args = _ns(id="p1", fields=["name=NewName"])
        process_receipts.cmd_project_update(args, fake_client)
        fake_client.update_project.assert_called_once_with("p1", name="NewName")

    def test_cmd_project_delete(self, fake_client, capsys):
        args = _ns(id="p1")
        process_receipts.cmd_project_delete(args, fake_client)
        fake_client.delete_project.assert_called_once_with("p1")


class TestCmdCategories:
    def test_cmd_categories(self, fake_client, capsys):
        args = _ns()
        process_receipts.cmd_categories(args, fake_client)
        fake_client.list_categories.assert_called_once()

    def test_cmd_category_add(self, fake_client, capsys):
        args = _ns(name="Food", description="desc", color="#FF5733")
        process_receipts.cmd_category_add(args, fake_client)
        fake_client.create_category.assert_called_once_with(
            "Food", description="desc", color="#FF5733"
        )

    def test_cmd_category_delete(self, fake_client, capsys):
        args = _ns(name="Food")
        process_receipts.cmd_category_delete(args, fake_client)
        fake_client.delete_category.assert_called_once_with("Food")


class TestCmdVendors:
    def test_cmd_vendors(self, fake_client, capsys):
        args = _ns()
        process_receipts.cmd_vendors(args, fake_client)
        fake_client.list_vendors.assert_called_once()

    def test_cmd_vendor_add(self, fake_client, capsys):
        args = _ns(name="Store", category="Food")
        process_receipts.cmd_vendor_add(args, fake_client)
        fake_client.create_vendor.assert_called_once_with("Store", category="Food")

    def test_cmd_vendor_delete(self, fake_client, capsys):
        args = _ns(name="Store")
        process_receipts.cmd_vendor_delete(args, fake_client)
        fake_client.delete_vendor.assert_called_once_with("Store")


class TestCmdRules:
    def test_cmd_rules(self, fake_client, capsys):
        args = _ns()
        process_receipts.cmd_rules(args, fake_client)
        fake_client.list_rules.assert_called_once()

    def test_cmd_rule_create_valid_json(self, fake_client, capsys):
        args = _ns(
            type="transaction_rule",
            condition='{"vendor_contains": "Amazon"}',
            action='{"set_category": "Software"}',
            priority=5,
            disabled=False,
        )
        process_receipts.cmd_rule_create(args, fake_client)
        fake_client.create_rule.assert_called_once_with(
            rule_type="transaction_rule",
            condition={"vendor_contains": "Amazon"},
            action={"set_category": "Software"},
            priority=5,
            enabled=True,
        )

    def test_cmd_rule_create_invalid_json(self, fake_client, capsys):
        args = _ns(
            type="transaction_rule",
            condition="not json",
            action="not json",
            priority=None,
            disabled=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.cmd_rule_create(args, fake_client)
        assert exc_info.value.code == 1

    def test_cmd_rule_update(self, fake_client, capsys):
        args = _ns(id="r1", fields=["enabled=false"])
        process_receipts.cmd_rule_update(args, fake_client)
        fake_client.update_rule.assert_called_once_with("r1", enabled=False)

    def test_cmd_rule_delete(self, fake_client, capsys):
        args = _ns(id="r1")
        process_receipts.cmd_rule_delete(args, fake_client)
        fake_client.delete_rule.assert_called_once_with("r1")


class TestCmdWebhooks:
    def test_cmd_webhooks(self, fake_client, capsys):
        args = _ns()
        process_receipts.cmd_webhooks(args, fake_client)
        fake_client.list_webhooks.assert_called_once()

    def test_cmd_webhook_create_valid_events(self, fake_client, capsys):
        args = _ns(
            url="https://hook.url",
            events=["transaction.created", "batch.completed"],
            secret=None,
        )
        process_receipts.cmd_webhook_create(args, fake_client)
        fake_client.create_webhook.assert_called_once_with(
            "https://hook.url", ["transaction.created", "batch.completed"], secret=None
        )

    def test_cmd_webhook_create_invalid_events(self, fake_client, capsys):
        args = _ns(url="https://hook.url", events=["invalid.event"], secret=None)
        with pytest.raises(SystemExit) as exc_info:
            process_receipts.cmd_webhook_create(args, fake_client)
        assert exc_info.value.code == 1

    def test_cmd_webhook_delete(self, fake_client, capsys):
        args = _ns(id="wh1")
        process_receipts.cmd_webhook_delete(args, fake_client)
        fake_client.delete_webhook.assert_called_once_with("wh1")


class TestCmdExport:
    def test_export_with_output_inline_content(self, fake_client, capsys, tmp_path):
        fake_client.export_transactions.return_value = {
            "success": True,
            "data": {"content": "csv,data\n1,2"},
        }
        out_file = tmp_path / "out.csv"
        args = _ns(
            format="csv",
            start_date=None,
            end_date=None,
            project_id=None,
            category=None,
            output=str(out_file),
        )
        process_receipts.cmd_export(args, fake_client)
        assert out_file.read_text(encoding="utf-8") == "csv,data\n1,2"

    def test_export_with_output_no_content(self, fake_client, capsys, tmp_path):
        fake_client.export_transactions.return_value = {
            "success": True,
            "data": {"url": "https://download.url"},
        }
        out_file = tmp_path / "out.csv"
        args = _ns(
            format="csv",
            start_date=None,
            end_date=None,
            project_id=None,
            category=None,
            output=str(out_file),
        )
        process_receipts.cmd_export(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True

    def test_export_without_output(self, fake_client, capsys):
        args = _ns(
            format="csv",
            start_date=None,
            end_date=None,
            project_id=None,
            category=None,
            output=None,
        )
        process_receipts.cmd_export(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True


class TestCmdUsage:
    def test_cmd_usage(self, fake_client, capsys):
        args = _ns()
        process_receipts.cmd_usage(args, fake_client)
        fake_client.get_usage.assert_called_once()


class TestCmdBankStatements:
    def test_cmd_bank_statements(self, fake_client, capsys):
        args = _ns(limit=10, offset=5)
        process_receipts.cmd_bank_statements(args, fake_client)
        fake_client.list_bank_statements.assert_called_once_with(limit=10, offset=5)

    def test_cmd_bank_statement_get(self, fake_client, capsys):
        args = _ns(id="bs1")
        process_receipts.cmd_bank_statement_get(args, fake_client)
        fake_client.get_bank_statement.assert_called_once_with("bs1")

    def test_cmd_bank_statement_delete(self, fake_client, capsys):
        args = _ns(id="bs1")
        process_receipts.cmd_bank_statement_delete(args, fake_client)
        fake_client.delete_bank_statement.assert_called_once_with("bs1")

    def test_cmd_bank_statement_export_no_content(self, fake_client, capsys):
        fake_client.export_bank_statement.return_value = {
            "success": True,
            "data": {"url": "https://download.url"},
        }
        args = _ns(id="bs1", output=None)
        process_receipts.cmd_bank_statement_export(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True

    def test_cmd_bank_statement_export_url_fallback_with_output(
        self, fake_client, capsys, tmp_path
    ):
        fake_client.export_bank_statement.return_value = {
            "success": True,
            "data": {"url": "https://download.url"},
        }
        out_file = tmp_path / "export.csv"
        args = _ns(id="bs1", output=str(out_file))
        process_receipts.cmd_bank_statement_export(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True


class TestCmdBankTransactions:
    def test_cmd_bank_transactions(self, fake_client, capsys):
        args = _ns(statement_id="bs1", limit=10, offset=0)
        process_receipts.cmd_bank_transactions(args, fake_client)
        fake_client.list_bank_transactions.assert_called_once_with(
            statement_id="bs1", limit=10, offset=0
        )

    def test_cmd_bank_transaction_get(self, fake_client, capsys):
        args = _ns(id="bt1")
        process_receipts.cmd_bank_transaction_get(args, fake_client)
        fake_client.get_bank_transaction.assert_called_once_with("bt1")

    def test_cmd_bank_transaction_delete(self, fake_client, capsys):
        args = _ns(id="bt1")
        process_receipts.cmd_bank_transaction_delete(args, fake_client)
        fake_client.delete_bank_transaction.assert_called_once_with("bt1")


class TestCmdReconciliation:
    def test_cmd_reconciliation_links(self, fake_client, capsys):
        args = _ns(statement_id="bs1", limit=10, offset=0)
        process_receipts.cmd_reconciliation_links(args, fake_client)
        fake_client.list_reconciliation_links.assert_called_once_with(
            statement_id="bs1", limit=10, offset=0
        )

    def test_cmd_reconciliation_link_update(self, fake_client, capsys):
        args = _ns(id="rl1", fields=["status=confirmed"])
        process_receipts.cmd_reconciliation_link_update(args, fake_client)
        fake_client.update_reconciliation_link.assert_called_once_with(
            "rl1", status="confirmed"
        )

    def test_cmd_reconciliation_link_delete(self, fake_client, capsys):
        args = _ns(id="rl1")
        process_receipts.cmd_reconciliation_link_delete(args, fake_client)
        fake_client.delete_reconciliation_link.assert_called_once_with("rl1")

    def test_cmd_reconciliation_summary(self, fake_client, capsys):
        args = _ns(statement_id="bs1")
        process_receipts.cmd_reconciliation_summary(args, fake_client)
        fake_client.get_reconciliation_summary.assert_called_once_with("bs1")

    def test_cmd_reconciliation_export_without_output(self, fake_client, capsys):
        args = _ns(statement_id=None, format=None, output=None)
        process_receipts.cmd_reconciliation_export(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True

    def test_cmd_reconciliation_export_url_fallback_with_output(
        self, fake_client, capsys, tmp_path
    ):
        fake_client.export_reconciliation.return_value = {
            "success": True,
            "data": {"url": "https://download.url"},
        }
        out_file = tmp_path / "recon.csv"
        args = _ns(statement_id="bs1", format="csv", output=str(out_file))
        process_receipts.cmd_reconciliation_export(args, fake_client)
        out = capsys.readouterr().out
        assert json.loads(out)["success"] is True
