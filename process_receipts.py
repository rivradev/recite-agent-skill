#!/usr/bin/env python3
"""
Recite Skill CLI
Full access to the Recite API for AI agents and humans.

Usage:
    python process_receipts.py <subcommand> [options]
    python process_receipts.py --help
    python process_receipts.py <subcommand> --help

Backward-compatible: calling with a directory as the first argument still
triggers the 'scan-dir' workflow (equivalent to running `scan-dir <dir>`).
"""

import argparse
import csv
import glob
import json
import os
import re
import requests
import sys
import tempfile
import time
from datetime import datetime

from recite_client import ReciteClient, ReciteError

# ─── Constants ────────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.expanduser("~/.config/recite/config.json")
CSV_NAME    = "bookkeeping_transactions.CSV"
LTM_FILE    = "long_term_memory.md"

SUPPORTED_EXTENSIONS = [
    "*.jpg", "*.jpeg", "*.png", "*.pdf",
    "*.JPG", "*.JPEG", "*.PNG", "*.PDF",
]

VALID_EVENTS = [
    "transaction.created",
    "transaction.updated",
    "transaction.deleted",
    "batch.completed",
]

VALID_RULE_TYPES = [
    "transaction_rule",
    "vendor_category",
    "default_project",
    "processing_preference",
]

# ─── Config / Auth ────────────────────────────────────────────────────────────

def get_api_key() -> str | None:
    """Load API key from config file or environment variable."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            if "api_key" in cfg:
                return cfg["api_key"]
        except Exception:
            pass
    return os.environ.get("RECITE_API_KEY")


def require_api_key() -> str:
    """Return the API key or exit with a clear error message."""
    key = get_api_key()
    if not key:
        print(json.dumps({
            "error": "Recite API key not found.",
            "hint":  (
                "Set the RECITE_API_KEY environment variable or create "
                "~/.config/recite/config.json with {\"api_key\": \"re_live_...\"}"
            ),
            "docs": "https://recite.rivra.dev/settings/api",
        }, indent=2))
        sys.exit(1)
    return key


# ─── Output Helpers ───────────────────────────────────────────────────────────

def output_json(data: object) -> None:
    """Print data as pretty-printed JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def output_failure(
    code: str,
    message: str,
    details: dict | None = None,
    http_status: int | None = None,
) -> None:
    """Print a structured JSON error object to stdout."""
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    if http_status is not None:
        payload["http_status"] = http_status
    output_json(payload)


def output_error(error: ReciteError) -> None:
    """Print a ReciteError as a structured JSON error object."""
    output_failure(
        code=error.code,
        message=error.message,
        details=error.details,
        http_status=error.status,
    )


# ─── CSV Helpers (used by scan-dir) ──────────────────────────────────────────

def read_ltm(skill_path: str) -> str:
    """Read and return the contents of long_term_memory.md."""
    ltm_path = os.path.join(skill_path, LTM_FILE)
    if os.path.exists(ltm_path):
        with open(ltm_path, encoding="utf-8") as f:
            return f.read()
    return ""


def get_processed_filenames(csv_path: str) -> set:
    """Return all filenames already represented in the CSV ledger."""
    if not os.path.exists(csv_path):
        return set()
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                processed = set()
                for row in reader:
                    for key in ("OriginalFilename", "NewFilename"):
                        value = row.get(key)
                        if value:
                            processed.add(value)
                return processed
    except Exception:
        pass
    return set()


def flatten_dict(d: dict, parent_key: str = "", sep: str = "_") -> dict:
    """Recursively flatten a nested dict for CSV storage."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def update_csv(csv_path: str, new_row: dict) -> None:
    """Append a row to the CSV ledger, expanding columns if the API adds new fields.

    Uses an atomic temp-file + os.replace() write to prevent data loss on crash.
    """
    file_exists = os.path.exists(csv_path)
    existing_data: list = []
    existing_headers: list = []

    if file_exists:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_headers = list(reader.fieldnames or [])
            existing_data = list(reader)

    new_fields = [k for k in new_row if k not in existing_headers]

    if new_fields:
        print(f"  [schema] New columns detected: {new_fields}")
        existing_headers += new_fields
        csv_dir = os.path.dirname(csv_path) or "."
        tmp_fd, tmp_path = tempfile.mkstemp(dir=csv_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", newline="", encoding="utf-8") as tmp_f:
                writer = csv.DictWriter(tmp_f, fieldnames=existing_headers, restval="")
                writer.writeheader()
                writer.writerows(existing_data)
                writer.writerow(new_row)
            os.replace(tmp_path, csv_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    else:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=existing_headers, restval="")
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_row)


def unique_filename(target_dir: str, date: str, vendor: str, ext: str) -> str:
    """Return a collision-free filename like '2024-05-20_Starbucks.jpg'."""
    safe_vendor = re.sub(r'[<>:"/\\|?*]', "-", str(vendor))
    name = f"{date}_{safe_vendor}{ext}"
    path = os.path.join(target_dir, name)
    if not os.path.exists(path):
        return name
    base_ts = int(time.time())
    counter = 0
    while True:
        suffix = str(base_ts) if counter == 0 else f"{base_ts}_{counter}"
        name = f"{date}_{safe_vendor}_{suffix}{ext}"
        if not os.path.exists(os.path.join(target_dir, name)):
            return name
        counter += 1


def get_receipt_files(target_dir: str) -> list[str]:
    """Return supported receipt files without case-insensitive duplicates."""
    files = []
    seen = set()
    for ext in SUPPORTED_EXTENSIONS:
        for file_path in glob.glob(os.path.join(target_dir, ext)):
            normalized = os.path.normcase(os.path.normpath(file_path))
            if normalized in seen:
                continue
            seen.add(normalized)
            files.append(file_path)
    return files


# ─── Subcommand: scan-dir ─────────────────────────────────────────────────────

def cmd_scan_dir(args: argparse.Namespace, client: ReciteClient) -> None:
    """Scan every receipt in a directory: rename files + append to CSV ledger."""
    skill_path = args.skill_path or "."

    ltm = read_ltm(skill_path)
    if ltm:
        print("--- Long-Term Memory (Custom Rules) ---")
        print(ltm)
        print("---------------------------------------\n")

    target_dir = args.directory
    if not os.path.isdir(target_dir):
        print(f"Error: '{target_dir}' is not a directory.")
        sys.exit(1)

    files = get_receipt_files(target_dir)

    if not files:
        print(f"No receipt files found in '{target_dir}'.")
        return

    csv_path        = os.path.join(target_dir, CSV_NAME)
    already_done    = get_processed_filenames(csv_path)
    processed = skipped = errors = 0

    for file_path in files:
        basename = os.path.basename(file_path)
        if CSV_NAME in basename:
            continue

        if basename in already_done:
            print(f"  Skip: {basename} (already in ledger)")
            skipped += 1
            continue

        print(f"  Scan: {basename} ...")
        try:
            result = client.scan_file(
                file_path,
                project_id=getattr(args, "project_id", None),
                format=getattr(args, "format", None),
                auto_create_transaction=getattr(args, "auto_create_transaction", None),
                confidence_threshold=getattr(args, "confidence_threshold", None),
            )
        except ReciteError as e:
            print(f"  Error ({e.code}): {e.message}")
            errors += 1
            continue

        raw      = result.get("data", {})
        row_data = flatten_dict(raw.get("extracted_data", {}))
        row_data["scan_id"]          = raw.get("scan_id")
        row_data["transaction_type"] = raw.get("transaction_type")

        ext      = os.path.splitext(file_path)[1]
        date     = str(row_data.get("date", "UnknownDate"))
        vendor   = str(row_data.get("vendor", "UnknownVendor"))
        new_name = unique_filename(target_dir, date, vendor, ext)
        new_path = os.path.join(target_dir, new_name)

        actual_name = new_name
        try:
            os.rename(file_path, new_path)
        except OSError as e:
            print(f"  Warning: Could not rename '{basename}': {e}. Using original name.")
            actual_name = basename

        row_data["OriginalFilename"] = basename
        row_data["NewFilename"]      = actual_name
        update_csv(csv_path, row_data)
        print(f"  Done: {actual_name}")
        processed += 1

    print(f"\n--- Summary ---")
    print(f"  Processed : {processed}")
    print(f"  Skipped   : {skipped}")
    print(f"  Errors    : {errors}")
    print(f"  Ledger    : {csv_path}")
    if processed:
        quota = result.get("meta", {}).get("quota_remaining")  # type: ignore[name-defined]
        if quota is not None:
            print(f"  Quota left: {quota}")


# ─── Subcommand: scan ─────────────────────────────────────────────────────────

def cmd_scan(args: argparse.Namespace, client: ReciteClient) -> None:
    """Scan a single receipt file and print the full API response as JSON."""
    result = client.scan_file(
        args.file,
        project_id=getattr(args, "project_id", None),
        format=getattr(args, "format", None),
        auto_create_transaction=getattr(args, "auto_create_transaction", None),
        confidence_threshold=getattr(args, "confidence_threshold", None),
    )
    output_json(result)


# ─── Subcommand: scan-url ─────────────────────────────────────────────────────

def cmd_scan_url(args: argparse.Namespace, client: ReciteClient) -> None:
    """Scan a receipt image URL and print the full API response as JSON."""
    result = client.scan_url(
        args.url,
        project_id=getattr(args, "project_id", None),
        format=getattr(args, "format", None),
        auto_create_transaction=getattr(args, "auto_create_transaction", None),
        confidence_threshold=getattr(args, "confidence_threshold", None),
    )
    output_json(result)


# ─── Subcommand: scan-text ────────────────────────────────────────────────────

def cmd_scan_text(args: argparse.Namespace, client: ReciteClient) -> None:
    """Scan raw receipt text (read from a file or stdin) and return extracted data."""
    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    result = client.scan_text(
        text,
        project_id=getattr(args, "project_id", None),
        format=getattr(args, "format", None),
        auto_create_transaction=getattr(args, "auto_create_transaction", None),
        confidence_threshold=getattr(args, "confidence_threshold", None),
    )
    output_json(result)


# ─── Subcommand: get-scan ─────────────────────────────────────────────────────

def cmd_get_scan(args: argparse.Namespace, client: ReciteClient) -> None:
    """Retrieve a previously submitted scan by its ID."""
    output_json(client.get_scan(args.scan_id))


# ─── Subcommand: batch ────────────────────────────────────────────────────────

def cmd_batch(args: argparse.Namespace, client: ReciteClient) -> None:
    """Submit up to 20 files or URLs for asynchronous batch scanning."""
    if len(args.files) > 20:
        print(f"  Warning: Only the first 20 of {len(args.files)} items will be submitted.", file=sys.stderr)
    result = client.create_batch(args.files, project_id=getattr(args, "project_id", None))
    output_json(result)


# ─── Subcommand: batch-status ─────────────────────────────────────────────────

def cmd_batch_status(args: argparse.Namespace, client: ReciteClient) -> None:
    """Check the status of an asynchronous batch job."""
    output_json(client.get_batch_status(args.batch_id))


# ─── Subcommand: batch-results ────────────────────────────────────────────────

def cmd_batch_results(args: argparse.Namespace, client: ReciteClient) -> None:
    """Retrieve all extraction results for a completed batch job."""
    output_json(client.get_batch_results(args.batch_id))


# ─── Subcommand: batch-wait ───────────────────────────────────────────────────

def cmd_batch_wait(args: argparse.Namespace, client: ReciteClient) -> None:
    """Poll a batch job until it completes, then print results.

    Useful for agents that want a single blocking call instead of polling manually.
    """
    interval = max(2, args.interval)
    deadline = time.time() + args.timeout
    print(f"  Waiting for batch {args.batch_id} (timeout {args.timeout}s) ...", file=sys.stderr)

    while time.time() < deadline:
        status_resp = client.get_batch_status(args.batch_id)
        status = status_resp.get("data", {}).get("status", "")
        print(f"  Status: {status}", file=sys.stderr)
        if status == "completed":
            output_json(client.get_batch_results(args.batch_id))
            return
        if status == "failed":
            output_json(status_resp)
            sys.exit(1)
        time.sleep(interval)

    print(json.dumps({"error": "Batch timed out", "batch_id": args.batch_id}))
    sys.exit(1)


# ─── Subcommand: transactions ─────────────────────────────────────────────────

def cmd_transactions(args: argparse.Namespace, client: ReciteClient) -> None:
    """List transactions with optional filters."""
    output_json(client.list_transactions(
        start_date=args.start_date,
        end_date=args.end_date,
        category=args.category,
        vendor=args.vendor,
        project_id=args.project_id,
        limit=args.limit,
        offset=args.offset,
        sort=args.sort,
    ))


def cmd_transaction_get(args: argparse.Namespace, client: ReciteClient) -> None:
    """Get a single transaction by ID."""
    output_json(client.get_transaction(args.id))


def cmd_transaction_create(args: argparse.Namespace, client: ReciteClient) -> None:
    """Manually create a transaction record."""
    extra = _parse_kv_list(args.extra or [])
    try:
        total = float(args.total)
    except ValueError as exc:
        raise ValueError(f"Invalid total '{args.total}'. Expected a numeric amount.") from exc
    output_json(client.create_transaction(
        vendor=args.vendor,
        total=total,
        date=args.date,
        currency=args.currency or "USD",
        category=args.category,
        project_id=args.project_id,
        notes=args.notes,
        **extra,
    ))


def cmd_transaction_update(args: argparse.Namespace, client: ReciteClient) -> None:
    """Update one or more fields of an existing transaction."""
    fields = _parse_kv_list(args.fields)
    output_json(client.update_transaction(args.id, **fields))


def cmd_transaction_delete(args: argparse.Namespace, client: ReciteClient) -> None:
    """Permanently delete a transaction."""
    output_json(client.delete_transaction(args.id))


# ─── Subcommand: import ───────────────────────────────────────────────────────

def cmd_import(args: argparse.Namespace, client: ReciteClient) -> None:
    """Bulk-import up to 500 transactions from a JSON or CSV file.

    The JSON file must contain either a list of transaction objects or an object
    with a "transactions" key containing the list.
    For CSV, pass --format csv or use a file with a .csv extension.
    """
    is_csv = getattr(args, "format", None) == "csv" or args.file.lower().endswith(".csv")

    if is_csv:
        with open(args.file, encoding="utf-8") as f:
            data = f.read()
        output_json(client.import_csv(data))
    else:
        try:
            with open(args.file, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in import file: {exc.msg}") from exc
        if isinstance(data, dict) and "transactions" in data:
            data = data["transactions"]
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of transaction objects.")
        output_json(client.import_transactions(data))


# ─── Subcommand: summary ──────────────────────────────────────────────────────

def cmd_summary(args: argparse.Namespace, client: ReciteClient) -> None:
    """Get aggregate financial statistics."""
    output_json(client.get_summary(
        start_date=args.start_date,
        end_date=args.end_date,
        group_by=args.group_by,
        project_id=args.project_id,
    ))


# ─── Subcommand: projects ─────────────────────────────────────────────────────

def cmd_projects(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.list_projects())


def cmd_project_create(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.create_project(args.name, description=args.description))


def cmd_project_update(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.update_project(args.id, **_parse_kv_list(args.fields)))


def cmd_project_delete(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.delete_project(args.id))


# ─── Subcommand: categories ───────────────────────────────────────────────────

def cmd_categories(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.list_categories())


def cmd_category_add(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.create_category(
        args.name,
        description=args.description,
        color=args.color,
    ))


def cmd_category_delete(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.delete_category(args.name))


# ─── Subcommand: vendors ──────────────────────────────────────────────────────

def cmd_vendors(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.list_vendors())


def cmd_vendor_add(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.create_vendor(args.name, category=args.category))


def cmd_vendor_delete(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.delete_vendor(args.name))


# ─── Subcommand: rules ────────────────────────────────────────────────────────

def cmd_rules(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.list_rules())


def cmd_rule_create(args: argparse.Namespace, client: ReciteClient) -> None:
    try:
        condition = json.loads(args.condition)
        action    = json.loads(args.action)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in --condition or --action: {e}"}))
        sys.exit(1)
    output_json(client.create_rule(
        rule_type=args.type,
        condition=condition,
        action=action,
        priority=args.priority,
        enabled=not args.disabled,
    ))


def cmd_rule_update(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.update_rule(args.id, **_parse_kv_list(args.fields)))


def cmd_rule_delete(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.delete_rule(args.id))


# ─── Subcommand: webhooks ─────────────────────────────────────────────────────

def cmd_webhooks(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.list_webhooks())


def cmd_webhook_create(args: argparse.Namespace, client: ReciteClient) -> None:
    invalid = [e for e in args.events if e not in VALID_EVENTS]
    if invalid:
        print(json.dumps({"error": f"Unknown event(s): {invalid}. Valid: {VALID_EVENTS}"}))
        sys.exit(1)
    output_json(client.create_webhook(args.url, args.events, secret=args.secret))


def cmd_webhook_delete(args: argparse.Namespace, client: ReciteClient) -> None:
    output_json(client.delete_webhook(args.id))


# ─── Subcommand: export ───────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace, client: ReciteClient) -> None:
    """Export transactions. If --output is given, write content to a local file."""
    result = client.export_transactions(
        format=args.format or "csv",
        start_date=args.start_date,
        end_date=args.end_date,
        project_id=args.project_id,
        category=args.category,
    )
    if args.output:
        content = (result.get("data") or {}).get("content", "")
        if content:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(content)
            print(json.dumps({"exported_to": args.output, "bytes": len(content)}))
        else:
            # API returned a download URL instead of inline content
            output_json(result)
    else:
        output_json(result)


# ─── Subcommand: usage ────────────────────────────────────────────────────────

def cmd_usage(args: argparse.Namespace, client: ReciteClient) -> None:
    """View API scan quota and request metrics."""
    output_json(client.get_usage())


# ─── Utility ──────────────────────────────────────────────────────────────────

def _parse_kv_list(pairs: list[str]) -> dict:
    """Convert ['key=value', ...] into {'key': 'value', ...}."""
    result = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid field '{pair}'. Expected key=value format.")
        k, _, v = pair.partition("=")
        if not k:
            raise ValueError(f"Invalid field '{pair}': empty key.")
        # Auto-convert numeric strings to numbers for clean JSON payloads
        if v.lstrip("-").replace(".", "", 1).isdigit():
            result[k] = float(v) if "." in v else int(v)
        elif v.lower() in ("true", "false"):
            result[k] = v.lower() == "true"
        else:
            result[k] = v
    return result


# ─── Argument Parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="process_receipts.py",
        description=(
            "Recite Skill CLI — full Recite API access for AI agents.\n"
            "All subcommands except 'scan-dir' output JSON to stdout.\n\n"
            "API docs: https://recite.rivra.dev/docs/api"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    # ── scan-dir ──────────────────────────────────────────────────────────────
    p = sub.add_parser(
        "scan-dir",
        help="Scan a directory of receipts → rename files + append to CSV ledger",
        description="Original bookkeeping workflow: scan all images/PDFs in a folder.",
    )
    p.add_argument("directory",   help="Folder containing receipt images or PDFs")
    p.add_argument("skill_path",  nargs="?", default=".",
                   help="Skill folder path (used to locate long_term_memory.md)")
    p.add_argument("--project-id", dest="project_id",
                   help="Assign all scans to this Recite project ID")
    p.add_argument("--format", help="Response format hint ('json', 'csv', 'text')")
    p.add_argument("--auto-create-transaction", action="store_true", default=None,
                   help="Auto-create a transaction if confidence meets threshold")
    p.add_argument("--confidence-threshold", type=float, help="The confidence threshold")

    # ── scan ──────────────────────────────────────────────────────────────────
    p = sub.add_parser("scan", help="Scan a single receipt file → JSON")
    p.add_argument("file",        help="Path to image (.jpg/.png) or PDF")
    p.add_argument("--project-id", dest="project_id",
                   help="Assign scan to this project")
    p.add_argument("--format", help="Response format hint ('json', 'csv', 'text')")
    p.add_argument("--auto-create-transaction", action="store_true", default=None,
                   help="Auto-create a transaction if confidence meets threshold")
    p.add_argument("--confidence-threshold", type=float, help="The confidence threshold")

    # ── scan-url ──────────────────────────────────────────────────────────────
    p = sub.add_parser("scan-url", help="Scan a receipt image URL → JSON")
    p.add_argument("url",         help="URL of the image or PDF")
    p.add_argument("--project-id", dest="project_id",
                   help="Assign scan to this project")
    p.add_argument("--format", help="Response format hint ('json', 'csv', 'text')")
    p.add_argument("--auto-create-transaction", action="store_true", default=None,
                   help="Auto-create a transaction if confidence meets threshold")
    p.add_argument("--confidence-threshold", type=float, help="The confidence threshold")

    # ── scan-text ─────────────────────────────────────────────────────────────
    p = sub.add_parser("scan-text",
                       help="Scan raw receipt text from a file (or stdin with '-') → JSON")
    p.add_argument("file",        help="Text file path, or '-' to read from stdin")
    p.add_argument("--project-id", dest="project_id")
    p.add_argument("--format", help="Response format hint ('json', 'csv', 'text')")
    p.add_argument("--auto-create-transaction", action="store_true", default=None,
                   help="Auto-create a transaction if confidence meets threshold")
    p.add_argument("--confidence-threshold", type=float, help="The confidence threshold")

    # ── get-scan ──────────────────────────────────────────────────────────────
    p = sub.add_parser("get-scan", help="Retrieve a previous scan by ID → JSON")
    p.add_argument("scan_id",     help="Scan ID returned by the /scan endpoint")

    # ── batch ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("batch",
                       help="Submit up to 20 receipt files or URLs for async batch scanning → JSON")
    p.add_argument("files",       nargs="+", help="File paths or URLs to scan (max 20)")
    p.add_argument("--project-id", dest="project_id")

    # ── batch-status ──────────────────────────────────────────────────────────
    p = sub.add_parser("batch-status", help="Check batch job status → JSON")
    p.add_argument("batch_id",    help="Batch ID from the batch submission response")

    # ── batch-results ─────────────────────────────────────────────────────────
    p = sub.add_parser("batch-results", help="Retrieve all results for a completed batch → JSON")
    p.add_argument("batch_id",    help="Batch ID")

    # ── batch-wait ────────────────────────────────────────────────────────────
    p = sub.add_parser("batch-wait",
                       help="Poll a batch job until complete, then print results → JSON")
    p.add_argument("batch_id",    help="Batch ID")
    p.add_argument("--timeout",   type=int, default=300, help="Max wait in seconds (default 300)")
    p.add_argument("--interval",  type=int, default=5,   help="Poll interval in seconds (default 5)")

    # ── transactions ──────────────────────────────────────────────────────────
    p = sub.add_parser("transactions", help="List transactions with optional filters → JSON")
    p.add_argument("--start-date",  dest="start_date", metavar="YYYY-MM-DD")
    p.add_argument("--end-date",    dest="end_date",   metavar="YYYY-MM-DD")
    p.add_argument("--category",    help="Filter by category name")
    p.add_argument("--vendor",      help="Filter by vendor name")
    p.add_argument("--project-id",  dest="project_id")
    p.add_argument("--limit",       type=int, help="Max records to return")
    p.add_argument("--offset",      type=int, help="Records to skip (pagination)")
    p.add_argument("--sort",        help="Sort field, e.g. '-date', 'total'")

    # ── transaction-get ───────────────────────────────────────────────────────
    p = sub.add_parser("transaction-get", help="Get a single transaction by ID → JSON")
    p.add_argument("id",           help="Transaction ID")

    # ── transaction-create ────────────────────────────────────────────────────
    p = sub.add_parser("transaction-create",
                       help="Manually create a transaction → JSON")
    p.add_argument("--vendor",      required=True,  help="Vendor/merchant name")
    p.add_argument("--total",       required=True,  help="Amount (negative = refund)")
    p.add_argument("--date",        required=True,  metavar="YYYY-MM-DD")
    p.add_argument("--currency",    default="USD",  help="ISO 4217 code (default USD)")
    p.add_argument("--category",    help="Expense category")
    p.add_argument("--project-id",  dest="project_id")
    p.add_argument("--notes",       help="Free-form notes")
    p.add_argument("extra",         nargs="*",
                   help="Additional API fields as key=value pairs")

    # ── transaction-update ────────────────────────────────────────────────────
    p = sub.add_parser("transaction-update",
                       help="Update fields of a transaction → JSON")
    p.add_argument("id",           help="Transaction ID")
    p.add_argument("fields",       nargs="+",
                   help="Fields to update as key=value pairs  e.g. category=Travel notes=OK")

    # ── transaction-delete ────────────────────────────────────────────────────
    p = sub.add_parser("transaction-delete",
                       help="Permanently delete a transaction → JSON")
    p.add_argument("id",           help="Transaction ID")

    # ── import ────────────────────────────────────────────────────────────────
    p = sub.add_parser("import",
                       help="Bulk-import up to 500 transactions from a JSON or CSV file → JSON")
    p.add_argument("file",         help="JSON or CSV file. For JSON: a list [] or {\"transactions\": [...]}")
    p.add_argument("--format",     choices=["json", "csv"], help="Format of the file ('json', 'csv')")

    # ── summary ───────────────────────────────────────────────────────────────
    p = sub.add_parser("summary", help="Get aggregate financial statistics → JSON")
    p.add_argument("--start-date",  dest="start_date", metavar="YYYY-MM-DD")
    p.add_argument("--end-date",    dest="end_date",   metavar="YYYY-MM-DD")
    p.add_argument("--group-by",    dest="group_by",
                   help="Grouping dimension: category | vendor | month | project")
    p.add_argument("--project-id",  dest="project_id")

    # ── projects ──────────────────────────────────────────────────────────────
    sub.add_parser("projects", help="List all projects → JSON")

    p = sub.add_parser("project-create", help="Create a new project → JSON")
    p.add_argument("name",         help="Project name")
    p.add_argument("--description")

    p = sub.add_parser("project-update", help="Update a project → JSON")
    p.add_argument("id",           help="Project ID")
    p.add_argument("fields",       nargs="+", help="Fields as key=value pairs")

    p = sub.add_parser("project-delete", help="Delete a project → JSON")
    p.add_argument("id",           help="Project ID")

    # ── categories ────────────────────────────────────────────────────────────
    sub.add_parser("categories", help="List all categories (built-in + custom) → JSON")

    p = sub.add_parser("category-add", help="Add a custom expense category → JSON")
    p.add_argument("name",         help="Unique category name")
    p.add_argument("--description")
    p.add_argument("--color",      help="Hex color e.g. '#FF5733'")

    p = sub.add_parser("category-delete", help="Remove a custom category → JSON")
    p.add_argument("name",         help="Category name to remove")

    # ── vendors ───────────────────────────────────────────────────────────────
    sub.add_parser("vendors", help="List custom vendors → JSON")

    p = sub.add_parser("vendor-add",
                       help="Register a vendor for auto-categorization → JSON")
    p.add_argument("name",         help="Vendor name as it appears on receipts")
    p.add_argument("--category",   help="Default expense category for this vendor")

    p = sub.add_parser("vendor-delete", help="Remove a vendor → JSON")
    p.add_argument("name",         help="Vendor name to remove")

    # ── rules ─────────────────────────────────────────────────────────────────
    sub.add_parser("rules", help="List all automation rules → JSON")

    p = sub.add_parser("rule-create", help="Create an automation rule → JSON")
    p.add_argument("--type",       required=True, choices=VALID_RULE_TYPES,
                   dest="type",    help="Rule type")
    p.add_argument("--condition",  required=True,
                   help='JSON condition object, e.g. \'{"vendor_contains":"Amazon"}\'')
    p.add_argument("--action",     required=True,
                   help='JSON action object, e.g. \'{"set_category":"Software"}\'')
    p.add_argument("--priority",   type=int, help="Evaluation order (higher = first)")
    p.add_argument("--disabled",   action="store_true", help="Create the rule as disabled")

    p = sub.add_parser("rule-update", help="Update an automation rule → JSON")
    p.add_argument("id",           help="Rule ID")
    p.add_argument("fields",       nargs="+",
                   help="Fields as key=value pairs  e.g. enabled=false priority=10")

    p = sub.add_parser("rule-delete", help="Remove an automation rule → JSON")
    p.add_argument("id",           help="Rule ID")

    # ── webhooks ──────────────────────────────────────────────────────────────
    sub.add_parser("webhooks", help="List all registered webhooks → JSON")

    p = sub.add_parser("webhook-create", help="Register a webhook endpoint → JSON")
    p.add_argument("url",          help="HTTPS endpoint URL")
    p.add_argument("events",       nargs="+",
                   help=(
                       "Events to subscribe to. Valid values: "
                       + ", ".join(VALID_EVENTS)
                   ))
    p.add_argument("--secret",     help="HMAC-SHA256 signing secret (recommended)")

    p = sub.add_parser("webhook-delete", help="Unregister a webhook → JSON")
    p.add_argument("id",           help="Webhook ID")

    # ── export ────────────────────────────────────────────────────────────────
    p = sub.add_parser("export",
                       help="Export transactions as CSV or JSON → JSON (or file with -o)")
    p.add_argument("--format",      choices=["csv", "json"], default="csv")
    p.add_argument("--start-date",  dest="start_date", metavar="YYYY-MM-DD")
    p.add_argument("--end-date",    dest="end_date",   metavar="YYYY-MM-DD")
    p.add_argument("--project-id",  dest="project_id")
    p.add_argument("--category")
    p.add_argument("--output", "-o",
                   help="Write inline export content to this local file path")

    # ── usage ─────────────────────────────────────────────────────────────────
    sub.add_parser("usage", help="View API quota and request metrics → JSON")

    return parser


# ─── Dispatch Table ───────────────────────────────────────────────────────────

COMMAND_MAP = {
    "scan-dir":            cmd_scan_dir,
    "scan":                cmd_scan,
    "scan-url":            cmd_scan_url,
    "scan-text":           cmd_scan_text,
    "get-scan":            cmd_get_scan,
    "batch":               cmd_batch,
    "batch-status":        cmd_batch_status,
    "batch-results":       cmd_batch_results,
    "batch-wait":          cmd_batch_wait,
    "transactions":        cmd_transactions,
    "transaction-get":     cmd_transaction_get,
    "transaction-create":  cmd_transaction_create,
    "transaction-update":  cmd_transaction_update,
    "transaction-delete":  cmd_transaction_delete,
    "import":              cmd_import,
    "summary":             cmd_summary,
    "projects":            cmd_projects,
    "project-create":      cmd_project_create,
    "project-update":      cmd_project_update,
    "project-delete":      cmd_project_delete,
    "categories":          cmd_categories,
    "category-add":        cmd_category_add,
    "category-delete":     cmd_category_delete,
    "vendors":             cmd_vendors,
    "vendor-add":          cmd_vendor_add,
    "vendor-delete":       cmd_vendor_delete,
    "rules":               cmd_rules,
    "rule-create":         cmd_rule_create,
    "rule-update":         cmd_rule_update,
    "rule-delete":         cmd_rule_delete,
    "webhooks":            cmd_webhooks,
    "webhook-create":      cmd_webhook_create,
    "webhook-delete":      cmd_webhook_delete,
    "export":              cmd_export,
    "usage":               cmd_usage,
}


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    # Backward-compat: if argv[1] looks like a path (not a known subcommand),
    # prepend 'scan-dir' to preserve the original calling convention.
    if (
        len(sys.argv) >= 2
        and sys.argv[1] not in COMMAND_MAP
        and not sys.argv[1].startswith("-")
    ):
        sys.argv.insert(1, "scan-dir")

    parser = build_parser()
    args   = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    api_key = require_api_key()
    client  = ReciteClient(api_key)

    try:
        COMMAND_MAP[args.command](args, client)
    except ReciteError as e:
        output_error(e)
        sys.exit(1)
    except ValueError as e:
        output_failure("INVALID_INPUT", str(e))
        sys.exit(1)
    except requests.RequestException as e:
        output_failure("REQUEST_FAILED", str(e))
        sys.exit(1)
    except FileNotFoundError as e:
        output_json({"error": f"File not found: {e.filename}"})
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
