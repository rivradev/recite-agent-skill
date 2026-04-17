import argparse
import pytest
from unittest.mock import MagicMock
import process_receipts
from recite_client import ReciteClient, ReciteError
from tests.conftest import FakeResponse


# ─── Client-level tests: Bank Statements ─────────────────────────────────────


def test_client_upload_bank_statement():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"id": "bs_1"}}
    )
    client._session = mock_session

    result = client.upload_bank_statement(
        "date,description,amount\n2026-01-01,Pay,100.0"
    )

    mock_session.request.assert_called_once_with(
        "POST",
        "https://recite.rivra.dev/apiV1/api/v1/bank-statements",
        data="date,description,amount\n2026-01-01,Pay,100.0",
        headers={"Content-Type": "text/csv"},
        timeout=60,
    )
    assert result == {"success": True, "data": {"id": "bs_1"}}


def test_client_upload_bank_statement_error():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {
            "success": False,
            "error": {"code": "INVALID_CSV", "message": "Bad CSV format"},
        },
        status_code=400,
    )
    client._session = mock_session

    with pytest.raises(ReciteError) as exc_info:
        client.upload_bank_statement("bad,data")
    assert exc_info.value.code == "INVALID_CSV"
    assert "Bad CSV format" in exc_info.value.message


def test_client_list_bank_statements():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True, "data": []})
    client._session = mock_session

    result = client.list_bank_statements(limit=10, offset=5)

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/bank-statements",
        params={"limit": 10, "offset": 5},
        timeout=60,
    )
    assert result == {"success": True, "data": []}


def test_client_get_bank_statement():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"id": "bs_abc"}}
    )
    client._session = mock_session

    result = client.get_bank_statement("bs_abc")

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/bank-statements/bs_abc",
        timeout=60,
    )
    assert result["data"]["id"] == "bs_abc"


def test_client_delete_bank_statement():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    client.delete_bank_statement("bs_abc")

    mock_session.request.assert_called_once_with(
        "DELETE",
        "https://recite.rivra.dev/apiV1/api/v1/bank-statements/bs_abc",
        timeout=60,
    )


def test_client_export_bank_statement():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"content": "date,desc,amount"}}
    )
    client._session = mock_session

    result = client.export_bank_statement("bs_abc")

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/bank-statements/bs_abc/export",
        timeout=60,
    )
    assert result["data"]["content"] == "date,desc,amount"


# ─── Client-level tests: Bank Transactions ───────────────────────────────────


def test_client_list_bank_transactions():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True, "data": []})
    client._session = mock_session

    result = client.list_bank_transactions(statement_id="bs_abc", limit=50)

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/bank-transactions",
        params={"statement_id": "bs_abc", "limit": 50},
        timeout=60,
    )
    assert result == {"success": True, "data": []}


def test_client_get_bank_transaction():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"id": "bt_abc"}}
    )
    client._session = mock_session

    result = client.get_bank_transaction("bt_abc")

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/bank-transactions/bt_abc",
        timeout=60,
    )
    assert result["data"]["id"] == "bt_abc"


def test_client_update_bank_transaction():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    client.update_bank_transaction("bt_abc", notes="Cleared", amount=100.0)

    mock_session.request.assert_called_once_with(
        "PATCH",
        "https://recite.rivra.dev/apiV1/api/v1/bank-transactions/bt_abc",
        json={"notes": "Cleared", "amount": 100.0},
        timeout=60,
    )


def test_client_delete_bank_transaction():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    client.delete_bank_transaction("bt_abc")

    mock_session.request.assert_called_once_with(
        "DELETE",
        "https://recite.rivra.dev/apiV1/api/v1/bank-transactions/bt_abc",
        timeout=60,
    )


# ─── Client-level tests: Reconciliation ──────────────────────────────────────


def test_client_create_reconciliation_link():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"id": "rl_1"}}
    )
    client._session = mock_session

    result = client.create_reconciliation_link("tx_abc", "bt_xyz")

    mock_session.request.assert_called_once_with(
        "POST",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/links",
        json={"transaction_id": "tx_abc", "bank_transaction_id": "bt_xyz"},
        timeout=60,
    )
    assert result["data"]["id"] == "rl_1"


def test_client_list_reconciliation_links():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True, "data": []})
    client._session = mock_session

    result = client.list_reconciliation_links(statement_id="bs_abc", limit=10)

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/links",
        params={"statement_id": "bs_abc", "limit": 10},
        timeout=60,
    )
    assert result == {"success": True, "data": []}


def test_client_update_reconciliation_link():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    client.update_reconciliation_link("rl_abc", status="confirmed")

    mock_session.request.assert_called_once_with(
        "PATCH",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/links/rl_abc",
        json={"status": "confirmed"},
        timeout=60,
    )


def test_client_delete_reconciliation_link():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    client.delete_reconciliation_link("rl_abc")

    mock_session.request.assert_called_once_with(
        "DELETE",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/links/rl_abc",
        timeout=60,
    )


def test_client_auto_match_reconciliation():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"matched": 5}}
    )
    client._session = mock_session

    result = client.auto_match_reconciliation("bs_abc")

    mock_session.request.assert_called_once_with(
        "POST",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/auto-match",
        json={"statement_id": "bs_abc"},
        timeout=60,
    )
    assert result["data"]["matched"] == 5


def test_client_get_reconciliation_summary():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"total": 10}}
    )
    client._session = mock_session

    result = client.get_reconciliation_summary("bs_abc")

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/summary",
        params={"statement_id": "bs_abc"},
        timeout=60,
    )
    assert result["data"]["total"] == 10


def test_client_export_reconciliation():
    client = ReciteClient("test_key")
    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": True, "data": {"content": "id,status\n1,matched"}}
    )
    client._session = mock_session

    result = client.export_reconciliation(statement_id="bs_abc", format="csv")

    mock_session.request.assert_called_once_with(
        "GET",
        "https://recite.rivra.dev/apiV1/api/v1/reconciliation/export",
        params={"statement_id": "bs_abc", "format": "csv"},
        timeout=60,
    )
    assert result["data"]["content"] == "id,status\n1,matched"


# ─── CLI-level tests ─────────────────────────────────────────────────────────


def test_cmd_bank_statement_upload(tmp_path):
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.upload_bank_statement.return_value = {
        "success": True,
        "data": {"id": "bs_1"},
    }

    csv_file = tmp_path / "stmt.csv"
    csv_file.write_text("date,desc,amount\n2026-01-01,Pay,100", encoding="utf-8")

    args = argparse.Namespace(file=str(csv_file))
    process_receipts.cmd_bank_statement_upload(args, mock_client)

    mock_client.upload_bank_statement.assert_called_once_with(
        "date,desc,amount\n2026-01-01,Pay,100"
    )


def test_cmd_bank_statement_export_with_output(tmp_path):
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.export_bank_statement.return_value = {
        "success": True,
        "data": {"content": "date,desc,amount"},
    }

    output_file = tmp_path / "export.csv"
    args = argparse.Namespace(id="bs_abc", output=str(output_file))
    process_receipts.cmd_bank_statement_export(args, mock_client)

    assert output_file.read_text(encoding="utf-8") == "date,desc,amount"


def test_cmd_bank_transaction_update():
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.update_bank_transaction.return_value = {"success": True}

    args = argparse.Namespace(id="bt_abc", fields=["notes=Cleared", "amount=100"])
    process_receipts.cmd_bank_transaction_update(args, mock_client)

    mock_client.update_bank_transaction.assert_called_once_with(
        "bt_abc", notes="Cleared", amount=100
    )


def test_cmd_reconciliation_link_create():
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.create_reconciliation_link.return_value = {"success": True}

    args = argparse.Namespace(transaction_id="tx_abc", bank_transaction_id="bt_xyz")
    process_receipts.cmd_reconciliation_link_create(args, mock_client)

    mock_client.create_reconciliation_link.assert_called_once_with("tx_abc", "bt_xyz")


def test_cmd_reconciliation_auto_match():
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.auto_match_reconciliation.return_value = {
        "success": True,
        "data": {"matched": 3},
    }

    args = argparse.Namespace(statement_id="bs_abc")
    process_receipts.cmd_reconciliation_auto_match(args, mock_client)

    mock_client.auto_match_reconciliation.assert_called_once_with("bs_abc")


def test_cmd_reconciliation_export(tmp_path):
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.export_reconciliation.return_value = {
        "success": True,
        "data": {"content": "id,status\n1,matched"},
    }

    output_file = tmp_path / "recon.csv"
    args = argparse.Namespace(
        statement_id="bs_abc", format="csv", output=str(output_file)
    )
    process_receipts.cmd_reconciliation_export(args, mock_client)

    assert output_file.read_text(encoding="utf-8") == "id,status\n1,matched"
