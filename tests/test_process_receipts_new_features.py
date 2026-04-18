import argparse
import pytest
from unittest.mock import MagicMock
import process_receipts
from recite_client import ReciteClient, ReciteError
from tests.conftest import FakeResponse


def test_scan_url_command(monkeypatch, capsys):
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.scan_url.return_value = {"success": True, "data": {"test": "ok"}}

    args = argparse.Namespace(
        url="https://example.com/image.jpg",
        project_id="proj_1",
        format="json",
        auto_create_transaction=True,
        confidence_threshold=0.8,
    )

    process_receipts.cmd_scan_url(args, mock_client)

    mock_client.scan_url.assert_called_once_with(
        "https://example.com/image.jpg",
        project_id="proj_1",
        format="json",
        auto_create_transaction=True,
        confidence_threshold=0.8,
    )


def test_batch_with_urls(monkeypatch):
    mock_client = MagicMock(spec=ReciteClient)

    args = argparse.Namespace(
        files=["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
        project_id=None,
    )

    process_receipts.cmd_batch(args, mock_client)

    mock_client.create_batch.assert_called_once_with(
        ["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
        project_id=None,
    )


def test_import_csv_command(monkeypatch, capsys, tmp_path):
    mock_client = MagicMock(spec=ReciteClient)
    mock_client.import_csv.return_value = {"success": True}

    csv_file = tmp_path / "test.csv"
    csv_file.write_text("vendor,total,date\nStore,10.0,2024-01-01", encoding="utf-8")

    args = argparse.Namespace(file=str(csv_file), format=None)

    process_receipts.cmd_import(args, mock_client)

    mock_client.import_csv.assert_called_once_with(
        "vendor,total,date\nStore,10.0,2024-01-01"
    )


def test_client_import_csv(monkeypatch):
    client = ReciteClient("test_key")

    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    result = client.import_csv("vendor,total,date\nStore,10.0,2024-01-01")

    mock_session.request.assert_called_once_with(
        "POST",
        "https://recite.rivra.dev/apiV1/api/v1/import/transactions",
        data="vendor,total,date\nStore,10.0,2024-01-01",
        headers={"Content-Type": "text/csv"},
        timeout=60,
    )
    assert result == {"success": True}


def test_client_import_csv_error(monkeypatch):
    client = ReciteClient("test_key")

    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse(
        {"success": False, "error": {"code": "INVALID_FORMAT", "message": "Bad CSV"}},
        status_code=400,
    )
    client._session = mock_session

    with pytest.raises(ReciteError) as exc_info:
        client.import_csv("bad,data")

    assert exc_info.value.code == "INVALID_FORMAT"
    assert "Bad CSV" in exc_info.value.message


def test_client_scan_url(monkeypatch):
    client = ReciteClient("test_key")

    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True, "data": {}})
    client._session = mock_session

    result = client.scan_url(
        "https://example.com/image.jpg", auto_create_transaction=True, format="json"
    )

    mock_session.request.assert_called_once_with(
        "POST",
        "https://recite.rivra.dev/apiV1/api/v1/scan",
        json={
            "image_url": "https://example.com/image.jpg",
            "auto_create_transaction": True,
            "format": "json",
        },
        timeout=60,
    )
    assert result == {"success": True, "data": {}}


def test_client_create_batch_urls(monkeypatch):
    client = ReciteClient("test_key")

    mock_session = MagicMock()
    mock_session.request.return_value = FakeResponse({"success": True})
    client._session = mock_session

    result = client.create_batch(
        ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
    )

    mock_session.request.assert_called_once_with(
        "POST",
        "https://recite.rivra.dev/apiV1/api/v1/batch/scans",
        json={
            "images": [
                {"image_url": "https://example.com/img1.jpg"},
                {"image_url": "https://example.com/img2.jpg"},
            ]
        },
        timeout=60,
    )
    assert result == {"success": True}
