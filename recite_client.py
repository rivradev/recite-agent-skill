"""
Recite API Client
Full wrapper for all public endpoints at https://recite.rivra.dev/apiV1/api/v1

Usage:
    from recite_client import ReciteClient, ReciteError
    client = ReciteClient(api_key="re_live_...")
    result = client.scan_file("receipt.jpg")
"""

import base64
import os
import requests
from typing import Any, Dict, List, Optional

BASE_URL = "https://recite.rivra.dev/apiV1/api/v1"


class ReciteError(Exception):
    """Raised for any non-success response from the Recite API."""

    def __init__(self, code: str, message: str, details: dict = None, status: int = None):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status = status
        super().__init__(f"[{code}] {message}")


class ReciteClient:
    """Thread-safe client for the Recite API. Reuses an underlying requests.Session."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Execute a request and return the parsed response dict.

        Raises ReciteError for API-level failures.
        Raises requests.HTTPError for unexpected non-JSON responses.
        """
        url = f"{BASE_URL}{path}"
        resp = self._session.request(method, url, timeout=60, **kwargs)

        try:
            body = resp.json()
        except ValueError:
            resp.raise_for_status()
            return {}

        if not body.get("success", False):
            err = body.get("error", {})
            raise ReciteError(
                code=err.get("code", "UNKNOWN"),
                message=err.get("message", "Unknown error"),
                details=err.get("details", {}),
                status=resp.status_code,
            )

        return body

    @staticmethod
    def _encode_file(file_path: str) -> str:
        """Return a data-URI string for the given image/PDF file."""
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".pdf":  "application/pdf",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif":  "image/gif",
        }
        if ext not in mime_map:
            supported = ", ".join(sorted(mime_map))
            raise ValueError(
                f"Unsupported file extension '{ext or '[none]'}'. "
                f"Supported extensions: {supported}"
            )
        mime = mime_map[ext]
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    # ─── Scanning ─────────────────────────────────────────────────────────────

    def scan_file(
        self,
        file_path: str,
        project_id: Optional[str] = None,
        format: Optional[str] = None,
        auto_create_transaction: Optional[bool] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Dict:
        """POST /scan — Extract structured data from a receipt image or PDF.

        Args:
            file_path:  Local path to a .jpg, .jpeg, .png, or .pdf file.
            project_id: Optional Recite project to assign this scan to.
            format:     Response format hint ('json', 'csv', 'text').
            auto_create_transaction: Auto-create a transaction if confidence meets threshold.
            confidence_threshold: The confidence threshold.

        Returns:
            Full API response dict with success, data, and meta fields.
        """
        payload: Dict[str, Any] = {"image_base64": self._encode_file(file_path)}
        if project_id:
            payload["project_id"] = project_id
        if format:
            payload["format"] = format
        if auto_create_transaction is not None:
            payload["auto_create_transaction"] = auto_create_transaction
        if confidence_threshold is not None:
            payload["confidence_threshold"] = confidence_threshold
        return self._request("POST", "/scan", json=payload)

    def scan_url(
        self,
        image_url: str,
        project_id: Optional[str] = None,
        format: Optional[str] = None,
        auto_create_transaction: Optional[bool] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Dict:
        """POST /scan — Extract structured data from a receipt image URL.

        Args:
            image_url:  URL of a .jpg, .jpeg, .png, or .pdf file.
            project_id: Optional Recite project to assign this scan to.
            format:     Response format hint ('json', 'csv', 'text').
            auto_create_transaction: Auto-create a transaction if confidence meets threshold.
            confidence_threshold: The confidence threshold.

        Returns:
            Full API response dict with success, data, and meta fields.
        """
        payload: Dict[str, Any] = {"image_url": image_url}
        if project_id:
            payload["project_id"] = project_id
        if format:
            payload["format"] = format
        if auto_create_transaction is not None:
            payload["auto_create_transaction"] = auto_create_transaction
        if confidence_threshold is not None:
            payload["confidence_threshold"] = confidence_threshold
        return self._request("POST", "/scan", json=payload)

    def scan_text(
        self,
        text: str,
        project_id: Optional[str] = None,
        format: Optional[str] = None,
        auto_create_transaction: Optional[bool] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Dict:
        """POST /scan — Extract structured data from raw receipt text.

        Args:
            text:       Plain-text representation of a receipt.
            project_id: Optional Recite project to assign this scan to.
            format:     Response format hint ('json', 'csv', 'text').
            auto_create_transaction: Auto-create a transaction if confidence meets threshold.
            confidence_threshold: The confidence threshold.
        """
        payload: Dict[str, Any] = {"text": text}
        if project_id:
            payload["project_id"] = project_id
        if format:
            payload["format"] = format
        if auto_create_transaction is not None:
            payload["auto_create_transaction"] = auto_create_transaction
        if confidence_threshold is not None:
            payload["confidence_threshold"] = confidence_threshold
        return self._request("POST", "/scan", json=payload)

    def get_scan(self, scan_id: str) -> Dict:
        """GET /scan/{id} — Retrieve a previously submitted scan result.

        Args:
            scan_id: The scan ID returned by scan_file() or scan_text().
        """
        return self._request("GET", f"/scan/{scan_id}")

    # ─── Batch Scanning ───────────────────────────────────────────────────────

    def create_batch(
        self,
        items: List[str],
        project_id: Optional[str] = None,
    ) -> Dict:
        """POST /batch/scans — Submit up to 20 items (files or URLs) for asynchronous processing.

        The API processes files in the background. Poll get_batch_status() until
        status == 'completed', then call get_batch_results() to retrieve extractions.

        Args:
            items: List of local file paths or URLs (max 20; extras are silently dropped).
            project_id: Optional project to assign all scans to.
        """
        images = []
        for item in items[:20]:
            if item.startswith("http://") or item.startswith("https://"):
                images.append({"image_url": item})
            else:
                images.append({
                    "image_base64": self._encode_file(item),
                    "filename": os.path.basename(item),
                })
        payload: Dict[str, Any] = {"images": images}
        if project_id:
            payload["project_id"] = project_id
        return self._request("POST", "/batch/scans", json=payload)

    def get_batch_status(self, batch_id: str) -> Dict:
        """GET /batch/scans/{id} — Check the status of an asynchronous batch job.

        Status values: 'pending', 'processing', 'completed', 'failed'.
        """
        return self._request("GET", f"/batch/scans/{batch_id}")

    def get_batch_results(self, batch_id: str) -> Dict:
        """GET /batch/scans/{id}/results — Retrieve all extraction results for a batch."""
        return self._request("GET", f"/batch/scans/{batch_id}/results")

    # ─── Transactions ─────────────────────────────────────────────────────────

    def list_transactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        vendor: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> Dict:
        """GET /transactions — List transactions with optional filters and pagination.

        Args:
            start_date: ISO date string 'YYYY-MM-DD' (inclusive).
            end_date:   ISO date string 'YYYY-MM-DD' (inclusive).
            category:   Filter by category name.
            vendor:     Filter by vendor name.
            project_id: Filter by project ID.
            limit:      Max records to return.
            offset:     Number of records to skip (for pagination).
            sort:       Sort field, e.g. 'date', '-date', 'total', '-total'.
        """
        params: Dict[str, Any] = {}
        if start_date:  params["start_date"]  = start_date
        if end_date:    params["end_date"]     = end_date
        if category:    params["category"]     = category
        if vendor:      params["vendor"]       = vendor
        if project_id:  params["project_id"]   = project_id
        if limit:       params["limit"]        = limit
        if offset:      params["offset"]       = offset
        if sort:        params["sort"]         = sort
        return self._request("GET", "/transactions", params=params)

    def get_transaction(self, tx_id: str) -> Dict:
        """GET /transactions/{id} — Retrieve a single transaction by ID."""
        return self._request("GET", f"/transactions/{tx_id}")

    def create_transaction(
        self,
        vendor: str,
        total: float,
        date: str,
        currency: str = "USD",
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        notes: Optional[str] = None,
        **extra: Any,
    ) -> Dict:
        """POST /transactions — Manually create a transaction record.

        Args:
            vendor:     Vendor/merchant name.
            total:      Transaction amount (positive for expense, negative for refund).
            date:       Transaction date 'YYYY-MM-DD'.
            currency:   ISO 4217 currency code (default 'USD').
            category:   Expense category name.
            project_id: Project to assign this transaction to.
            notes:      Free-form notes.
            **extra:    Any additional fields accepted by the API.
        """
        payload: Dict[str, Any] = {
            "vendor": vendor,
            "total": total,
            "date": date,
            "currency": currency,
        }
        if category:   payload["category"]   = category
        if project_id: payload["project_id"] = project_id
        if notes:      payload["notes"]      = notes
        payload.update(extra)
        return self._request("POST", "/transactions", json=payload)

    def update_transaction(self, tx_id: str, **fields: Any) -> Dict:
        """PATCH /transactions/{id} — Update one or more fields of a transaction.

        Pass keyword arguments corresponding to the fields you want to update.
        Example: client.update_transaction("abc123", category="Travel", notes="Q1 conf")
        """
        return self._request("PATCH", f"/transactions/{tx_id}", json=fields)

    def delete_transaction(self, tx_id: str) -> Dict:
        """DELETE /transactions/{id} — Permanently delete a transaction.

        Requires 'transactions:delete' API scope.
        """
        return self._request("DELETE", f"/transactions/{tx_id}")

    # ─── Import ───────────────────────────────────────────────────────────────

    def import_transactions(self, transactions: List[Dict]) -> Dict:
        """POST /import/transactions — Bulk-create up to 500 transaction records.

        Args:
            transactions: List of transaction dicts. Each should include at minimum
                          'vendor', 'total', and 'date'.

        Requires 'transactions:create' API scope.
        """
        return self._request("POST", "/import/transactions", json={"transactions": transactions})

    def import_csv(self, csv_data: str) -> Dict:
        """POST /import/transactions — Bulk-create up to 500 transaction records from CSV.

        Args:
            csv_data: Raw CSV string. Must include at minimum 'vendor', 'total', and 'date' columns.

        Requires 'transactions:create' API scope.
        """
        url = f"{BASE_URL}/import/transactions"
        # use raw requests instead of _request since we need to send raw text with text/csv
        resp = self._session.request(
            "POST",
            url,
            data=csv_data,
            headers={"Content-Type": "text/csv"},
            timeout=60,
        )

        try:
            body = resp.json()
        except ValueError:
            resp.raise_for_status()
            return {}

        if not body.get("success", False):
            err = body.get("error", {})
            raise ReciteError(
                code=err.get("code", "UNKNOWN"),
                message=err.get("message", "Unknown error"),
                details=err.get("details", {}),
                status=resp.status_code,
            )

        return body

    # ─── Projects ─────────────────────────────────────────────────────────────

    def list_projects(self) -> Dict:
        """GET /projects — List all projects."""
        return self._request("GET", "/projects")

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        **extra: Any,
    ) -> Dict:
        """POST /projects — Create a new project.

        Requires 'projects:write' API scope.
        """
        payload: Dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        payload.update(extra)
        return self._request("POST", "/projects", json=payload)

    def update_project(self, project_id: str, **fields: Any) -> Dict:
        """PATCH /projects/{id} — Update project fields.

        Requires 'projects:write' API scope.
        """
        return self._request("PATCH", f"/projects/{project_id}", json=fields)

    def delete_project(self, project_id: str) -> Dict:
        """DELETE /projects/{id} — Delete a project.

        Requires 'projects:write' API scope.
        """
        return self._request("DELETE", f"/projects/{project_id}")

    # ─── Summary & Analytics ──────────────────────────────────────────────────

    def get_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict:
        """GET /summary — Aggregate financial statistics.

        Args:
            start_date: ISO date 'YYYY-MM-DD' for period start.
            end_date:   ISO date 'YYYY-MM-DD' for period end.
            group_by:   Grouping dimension, e.g. 'category', 'vendor', 'month'.
            project_id: Scope analytics to a specific project.
        """
        params: Dict[str, Any] = {}
        if start_date:  params["start_date"]  = start_date
        if end_date:    params["end_date"]     = end_date
        if group_by:    params["group_by"]     = group_by
        if project_id:  params["project_id"]   = project_id
        return self._request("GET", "/summary", params=params)

    # ─── Webhooks ─────────────────────────────────────────────────────────────

    def list_webhooks(self) -> Dict:
        """GET /webhooks — List all registered webhook endpoints.

        Requires 'webhooks:manage' API scope.
        """
        return self._request("GET", "/webhooks")

    def create_webhook(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
    ) -> Dict:
        """POST /webhooks — Register a new webhook endpoint.

        Args:
            url:    HTTPS endpoint that will receive POST requests.
            events: List of event names to subscribe to. Valid values:
                    'transaction.created', 'transaction.updated',
                    'transaction.deleted', 'batch.completed'.
            secret: Optional HMAC-SHA256 signing secret. When set, Recite will
                    include an 'X-Recite-Signature' header on each delivery.

        Requires 'webhooks:manage' API scope.
        """
        payload: Dict[str, Any] = {"url": url, "events": events}
        if secret:
            payload["secret"] = secret
        return self._request("POST", "/webhooks", json=payload)

    def delete_webhook(self, webhook_id: str) -> Dict:
        """DELETE /webhooks/{id} — Unregister a webhook endpoint.

        Requires 'webhooks:manage' API scope.
        """
        return self._request("DELETE", f"/webhooks/{webhook_id}")

    # ─── Rules & Automation ───────────────────────────────────────────────────

    def list_rules(self) -> Dict:
        """GET /rules — List all automation rules ordered by priority.

        Requires 'rules:read' API scope.
        """
        return self._request("GET", "/rules")

    def create_rule(
        self,
        rule_type: str,
        condition: Dict,
        action: Dict,
        priority: Optional[int] = None,
        enabled: bool = True,
    ) -> Dict:
        """POST /rules — Create an automation rule.

        Args:
            rule_type:  One of 'transaction_rule', 'vendor_category',
                        'default_project', 'processing_preference'.
            condition:  Dict describing when the rule fires.
                        Example: {"vendor_contains": "Amazon"}
            action:     Dict describing what the rule does.
                        Example: {"set_category": "Software Services"}
            priority:   Integer priority (higher = evaluated first).
            enabled:    Whether the rule is active immediately (default True).

        Requires 'rules:write' API scope.
        """
        payload: Dict[str, Any] = {
            "type": rule_type,
            "condition": condition,
            "action": action,
            "enabled": enabled,
        }
        if priority is not None:
            payload["priority"] = priority
        return self._request("POST", "/rules", json=payload)

    def update_rule(self, rule_id: str, **fields: Any) -> Dict:
        """PATCH /rules/{id} — Update an automation rule.

        Requires 'rules:write' API scope.
        """
        return self._request("PATCH", f"/rules/{rule_id}", json=fields)

    def delete_rule(self, rule_id: str) -> Dict:
        """DELETE /rules/{id} — Remove an automation rule.

        Requires 'rules:write' API scope.
        """
        return self._request("DELETE", f"/rules/{rule_id}")

    # ─── Categories ───────────────────────────────────────────────────────────

    def list_categories(self) -> Dict:
        """GET /categories — List all built-in and custom categories."""
        return self._request("GET", "/categories")

    def create_category(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Dict:
        """POST /categories — Add a custom expense category (max 100 custom categories).

        Args:
            name:        Unique category name.
            description: Optional human-readable description.
            color:       Optional hex color code (e.g. '#FF5733') for UI display.
        """
        payload: Dict[str, Any] = {"name": name}
        if description: payload["description"] = description
        if color:       payload["color"]       = color
        return self._request("POST", "/categories", json=payload)

    def delete_category(self, name: str) -> Dict:
        """DELETE /categories/{name} — Remove a custom category by name.

        Built-in categories cannot be deleted.
        """
        return self._request("DELETE", f"/categories/{name}")

    # ─── Vendors ──────────────────────────────────────────────────────────────

    def list_vendors(self) -> Dict:
        """GET /vendors — List all custom vendors."""
        return self._request("GET", "/vendors")

    def create_vendor(
        self,
        name: str,
        category: Optional[str] = None,
        **extra: Any,
    ) -> Dict:
        """POST /vendors — Register a vendor for auto-categorization (max 500).

        Args:
            name:     Vendor name as it appears on receipts.
            category: Default expense category to assign to this vendor.
            **extra:  Any additional vendor fields accepted by the API.
        """
        payload: Dict[str, Any] = {"name": name}
        if category: payload["category"] = category
        payload.update(extra)
        return self._request("POST", "/vendors", json=payload)

    def delete_vendor(self, name: str) -> Dict:
        """DELETE /vendors/{name} — Remove a vendor by name."""
        return self._request("DELETE", f"/vendors/{name}")

    # ─── Export ───────────────────────────────────────────────────────────────

    def export_transactions(
        self,
        format: str = "csv",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        project_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict:
        """POST /export — Export transactions in CSV or JSON format.

        Args:
            format:     'csv' (default) or 'json'.
            start_date: Filter by start date 'YYYY-MM-DD'.
            end_date:   Filter by end date 'YYYY-MM-DD'.
            project_id: Scope export to a specific project.
            category:   Filter by category name.

        Requires 'export:create' API scope.
        The response data may contain a 'content' string or a 'url' download link.
        """
        payload: Dict[str, Any] = {"format": format}
        if start_date:  payload["start_date"]  = start_date
        if end_date:    payload["end_date"]     = end_date
        if project_id:  payload["project_id"]   = project_id
        if category:    payload["category"]     = category
        return self._request("POST", "/export", json=payload)

    # ─── Usage ────────────────────────────────────────────────────────────────

    def get_usage(self) -> Dict:
        """GET /usage — View scan quota and API request metrics.

        Returns remaining quota, daily/hourly limits, and usage counters.
        """
        return self._request("GET", "/usage")
