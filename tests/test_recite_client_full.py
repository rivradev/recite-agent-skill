import base64
import pytest
from unittest.mock import MagicMock

from recite_client import ReciteClient, ReciteError
from tests.conftest import FakeResponse, _case_dir


def _make_client():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True, "data": {}})
    client._session = mock_session
    return client


class TestHandleResponse:
    def test_non_json_success_returns_empty_dict(self):
        client = _make_client()
        resp = MagicMock()
        resp.json.side_effect = ValueError("no json")
        resp.status_code = 200
        resp.raise_for_status.return_value = None
        result = client._handle_response(resp)
        assert result == {}

    def test_non_json_error_raises_http_error(self):
        client = _make_client()
        resp = MagicMock()
        resp.json.side_effect = ValueError("no json")
        resp.status_code = 500
        resp.raise_for_status.side_effect = Exception("HTTP Error")
        with pytest.raises(Exception, match="HTTP Error"):
            client._handle_response(resp)


class TestEncodeFile:
    def test_encode_jpg(self, tmp_path):
        f = tmp_path / "test.jpg"
        content = b"\xff\xd8\xff\xe0test"
        f.write_bytes(content)
        result = ReciteClient._encode_file(str(f))
        expected_b64 = base64.b64encode(content).decode("utf-8")
        assert result == f"data:image/jpeg;base64,{expected_b64}"

    def test_encode_png(self, tmp_path):
        f = tmp_path / "test.png"
        content = b"\x89PNG\r\n"
        f.write_bytes(content)
        result = ReciteClient._encode_file(str(f))
        expected_b64 = base64.b64encode(content).decode("utf-8")
        assert result == f"data:image/png;base64,{expected_b64}"

    def test_encode_pdf(self, tmp_path):
        f = tmp_path / "test.pdf"
        content = b"%PDF-1.4"
        f.write_bytes(content)
        result = ReciteClient._encode_file(str(f))
        expected_b64 = base64.b64encode(content).decode("utf-8")
        assert result == f"data:application/pdf;base64,{expected_b64}"


class TestScanFile:
    def test_scan_file_with_all_params(self, tmp_path):
        f = tmp_path / "receipt.jpg"
        f.write_bytes(b"\xff\xd8test")
        client = _make_client()
        client.scan_file(
            str(f),
            project_id="p1",
            format="json",
            auto_create_transaction=True,
            confidence_threshold=0.9,
        )
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload["project_id"] == "p1"
        assert payload["format"] == "json"
        assert payload["auto_create_transaction"] is True
        assert payload["confidence_threshold"] == 0.9
        assert "image_base64" in payload


class TestScanUrl:
    def test_scan_url_with_all_params(self):
        client = _make_client()
        client.scan_url(
            "https://example.com/img.jpg",
            project_id="p1",
            format="json",
            auto_create_transaction=True,
            confidence_threshold=0.9,
        )
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {
            "image_url": "https://example.com/img.jpg",
            "project_id": "p1",
            "format": "json",
            "auto_create_transaction": True,
            "confidence_threshold": 0.9,
        }


class TestScanText:
    def test_scan_text_with_all_params(self):
        client = _make_client()
        client.scan_text(
            "receipt text",
            project_id="p1",
            format="json",
            auto_create_transaction=True,
            confidence_threshold=0.9,
        )
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {
            "text": "receipt text",
            "project_id": "p1",
            "format": "json",
            "auto_create_transaction": True,
            "confidence_threshold": 0.9,
        }


class TestGetScan:
    def test_get_scan(self):
        client = _make_client()
        client.get_scan("id123")
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/scan/id123", timeout=60
        )


class TestCreateBatch:
    def test_create_batch_with_file(self, tmp_path):
        f = tmp_path / "receipt.jpg"
        f.write_bytes(b"\xff\xd8test")
        client = _make_client()
        client.create_batch([str(f)])
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert len(payload["images"]) == 1
        assert "image_base64" in payload["images"][0]
        assert payload["images"][0]["filename"] == "receipt.jpg"

    def test_create_batch_silently_drops_over_20(self):
        client = _make_client()
        items = [f"https://example.com/img{i}.jpg" for i in range(25)]
        client.create_batch(items, project_id="p1")
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert len(payload["images"]) == 20
        assert payload["project_id"] == "p1"


class TestBatchStatusResults:
    def test_get_batch_status(self):
        client = _make_client()
        client.get_batch_status("bid")
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/batch/scans/bid", timeout=60
        )

    def test_get_batch_results(self):
        client = _make_client()
        client.get_batch_results("bid")
        client._session.request.assert_called_once_with(
            "GET",
            "https://recite.rivra.dev/apiV1/api/v1/batch/scans/bid/results",
            timeout=60,
        )


class TestTransactionMethods:
    def test_list_transactions_all_filters(self):
        client = _make_client()
        client.list_transactions(
            start_date="2024-01-01",
            end_date="2024-12-31",
            category="Food",
            vendor="Store",
            project_id="p1",
            limit=10,
            offset=5,
            sort="-date",
        )
        call_args = client._session.request.call_args
        params = call_args[1]["params"]
        assert params == {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "category": "Food",
            "vendor": "Store",
            "project_id": "p1",
            "limit": 10,
            "offset": 5,
            "sort": "-date",
        }

    def test_get_transaction(self):
        client = _make_client()
        client.get_transaction("tx1")
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/transactions/tx1", timeout=60
        )

    def test_create_transaction_with_extra_kwargs(self):
        client = _make_client()
        client.create_transaction(
            "Vendor",
            10.0,
            "2024-01-01",
            currency="EUR",
            category="Food",
            project_id="p1",
            notes="test",
            extra_field="val",
        )
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload["vendor"] == "Vendor"
        assert payload["total"] == 10.0
        assert payload["date"] == "2024-01-01"
        assert payload["currency"] == "EUR"
        assert payload["category"] == "Food"
        assert payload["project_id"] == "p1"
        assert payload["notes"] == "test"
        assert payload["extra_field"] == "val"

    def test_update_transaction(self):
        client = _make_client()
        client.update_transaction("tx1", category="Travel")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "PATCH"
        assert call_args[1]["json"] == {"category": "Travel"}

    def test_delete_transaction(self):
        client = _make_client()
        client.delete_transaction("tx1")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "DELETE"


class TestImportTransactions:
    def test_import_transactions(self):
        client = _make_client()
        client.import_transactions([{"vendor": "S", "total": 10, "date": "2024-01-01"}])
        call_args = client._session.request.call_args
        assert call_args[1]["json"] == {
            "transactions": [{"vendor": "S", "total": 10, "date": "2024-01-01"}]
        }


class TestProjectMethods:
    def test_list_projects(self):
        client = _make_client()
        client.list_projects()
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/projects", timeout=60
        )

    def test_create_project(self):
        client = _make_client()
        client.create_project("name", description="desc", extra_key="val")
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {"name": "name", "description": "desc", "extra_key": "val"}

    def test_update_project(self):
        client = _make_client()
        client.update_project("pid", name="new")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "PATCH"
        assert call_args[1]["json"] == {"name": "new"}

    def test_delete_project(self):
        client = _make_client()
        client.delete_project("pid")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "DELETE"


class TestGetSummary:
    def test_get_summary_all_params(self):
        client = _make_client()
        client.get_summary(
            start_date="2024-01-01",
            end_date="2024-12-31",
            group_by="category",
            project_id="p1",
        )
        call_args = client._session.request.call_args
        params = call_args[1]["params"]
        assert params == {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "group_by": "category",
            "project_id": "p1",
        }


class TestWebhookMethods:
    def test_list_webhooks(self):
        client = _make_client()
        client.list_webhooks()
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/webhooks", timeout=60
        )

    def test_create_webhook_with_secret(self):
        client = _make_client()
        client.create_webhook("https://hook.url", ["transaction.created"], secret="s")
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {
            "url": "https://hook.url",
            "events": ["transaction.created"],
            "secret": "s",
        }

    def test_delete_webhook(self):
        client = _make_client()
        client.delete_webhook("wid")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "DELETE"


class TestRuleMethods:
    def test_list_rules(self):
        client = _make_client()
        client.list_rules()
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/rules", timeout=60
        )

    def test_create_rule_with_priority(self):
        client = _make_client()
        client.create_rule(
            "transaction_rule",
            {"vendor_contains": "A"},
            {"set_category": "B"},
            priority=5,
        )
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload["type"] == "transaction_rule"
        assert payload["condition"] == {"vendor_contains": "A"}
        assert payload["action"] == {"set_category": "B"}
        assert payload["priority"] == 5
        assert payload["enabled"] is True

    def test_update_rule(self):
        client = _make_client()
        client.update_rule("rid", enabled=False)
        call_args = client._session.request.call_args
        assert call_args[0][0] == "PATCH"

    def test_delete_rule(self):
        client = _make_client()
        client.delete_rule("rid")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "DELETE"


class TestCategoryMethods:
    def test_list_categories(self):
        client = _make_client()
        client.list_categories()
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/categories", timeout=60
        )

    def test_create_category(self):
        client = _make_client()
        client.create_category("Food", description="d", color="#FF5733")
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {"name": "Food", "description": "d", "color": "#FF5733"}

    def test_delete_category(self):
        client = _make_client()
        client.delete_category("Food")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "DELETE"


class TestVendorMethods:
    def test_list_vendors(self):
        client = _make_client()
        client.list_vendors()
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/vendors", timeout=60
        )

    def test_create_vendor(self):
        client = _make_client()
        client.create_vendor("Store", category="Food")
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {"name": "Store", "category": "Food"}

    def test_delete_vendor(self):
        client = _make_client()
        client.delete_vendor("Store")
        call_args = client._session.request.call_args
        assert call_args[0][0] == "DELETE"


class TestExportTransactions:
    def test_export_transactions_all_params(self):
        client = _make_client()
        client.export_transactions(
            format="json",
            start_date="2024-01-01",
            end_date="2024-12-31",
            project_id="p1",
            category="Food",
        )
        call_args = client._session.request.call_args
        payload = call_args[1]["json"]
        assert payload == {
            "format": "json",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "project_id": "p1",
            "category": "Food",
        }


class TestGetUsage:
    def test_get_usage(self):
        client = _make_client()
        client.get_usage()
        client._session.request.assert_called_once_with(
            "GET", "https://recite.rivra.dev/apiV1/api/v1/usage", timeout=60
        )


class TestListBankTransactions:
    def test_no_optional_params(self):
        client = _make_client()
        client.list_bank_transactions()
        call_args = client._session.request.call_args
        assert call_args[1]["params"] == {}

    def test_with_offset(self):
        client = _make_client()
        client.list_bank_transactions(offset=10)
        call_args = client._session.request.call_args
        assert call_args[1]["params"] == {"offset": 10}


class TestExportReconciliation:
    def test_no_optional_params(self):
        client = _make_client()
        client.export_reconciliation()
        call_args = client._session.request.call_args
        assert call_args[1]["params"] == {}


class TestListReconciliationLinks:
    def test_with_offset(self):
        client = _make_client()
        client.list_reconciliation_links(offset=20)
        call_args = client._session.request.call_args
        assert call_args[1]["params"] == {"offset": 20}
