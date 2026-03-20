# Claude Code Guide: Recite Agent Skill 🦞🤵

This guide tells **Claude Code** how to operate the Recite bookkeeping skill.
The skill exposes the full Recite public API via a single CLI entry point.

## 📁 Key Files

| File | Role |
|------|------|
| `process_receipts.py` | Main CLI — all subcommands |
| `recite_client.py` | API client module (do not call directly) |
| `long_term_memory.md` | Persistent user rules — always read before acting |
| `bookkeeping_transactions.CSV` | Ledger generated in the scanned folder |

---

## 🔑 API Key — Check First

**Before any operation**, verify the API key is available:

```bash
# From environment
echo $RECITE_API_KEY

# Or from config
cat ~/.config/recite/config.json
```

If missing: stop immediately and tell the user to get a key at `https://recite.rivra.dev/settings/api`
then set `RECITE_API_KEY` or write `~/.config/recite/config.json` with `{"api_key": "re_live_..."}`.

---

## 🚀 Core Commands

### Bookkeeping Workflow (Original)
```bash
python skills/recite/process_receipts.py scan-dir <target_directory> skills/recite/
# Backward-compat (no subcommand) also works:
python skills/recite/process_receipts.py <target_directory> skills/recite/
```

### Check Available Quota Before Bulk Operations
```bash
python skills/recite/process_receipts.py usage
```

### Single File Scan
```bash
python skills/recite/process_receipts.py scan <file>
```

### Batch Scan (>5 files)
```bash
python skills/recite/process_receipts.py batch file1.jpg file2.pdf file3.png
python skills/recite/process_receipts.py batch-wait <batch_id> --timeout 120
```

### Financial Analytics
```bash
python skills/recite/process_receipts.py summary --group-by category
python skills/recite/process_receipts.py summary --start-date 2026-01-01 --end-date 2026-03-31
```

### Transaction Management
```bash
python skills/recite/process_receipts.py transactions --start-date 2026-01-01 --limit 100
python skills/recite/process_receipts.py transaction-update <id> category=Travel
python skills/recite/process_receipts.py transaction-delete <id>
```

### Export
```bash
python skills/recite/process_receipts.py export --format csv -o expenses.csv
python skills/recite/process_receipts.py export --format json --start-date 2026-01-01
```

### Automation Rules (persistent categorization)
```bash
python skills/recite/process_receipts.py rules
python skills/recite/process_receipts.py rule-create \
  --type vendor_category \
  --condition '{"vendor_contains": "Amazon"}' \
  --action '{"set_category": "Software Services"}' \
  --priority 10
```

---

## 🤖 Operation Guidelines

### 1. Read Long-Term Memory First
`scan-dir` always prints `long_term_memory.md` to stdout at startup.
Read it and apply every rule before acting on the scan output.

### 2. Prefer Batch for Large Directories
For > 5 files, use `batch` + `batch-wait` instead of looping `scan` calls.
This respects the 100 req/min rate limit.

### 3. Duplicate Prevention
`scan-dir` tracks `OriginalFilename` in the CSV. Re-running the same directory is safe — processed files are automatically skipped.

### 4. Schema-Aware Bookkeeping
If the Recite API adds new JSON fields, the CSV gains new columns automatically (atomic write). Existing rows are never modified.

### 5. File Renaming Convention
Files are renamed to `[YYYY-MM-DD]_[Vendor].[ext]`. On collision, a timestamp suffix is appended: `2024-05-20_Starbucks_1716220800.jpg`. Vendor names are sanitized to remove filesystem-unsafe characters.

### 6. All Non-scan-dir Subcommands Output JSON
Parse stdout as JSON when calling any subcommand other than `scan-dir`.
Errors are also JSON:
```json
{"success": false, "error": {"code": "...", "message": "..."}, "http_status": 429}
```

### 7. Scope Errors
If you see `INSUFFICIENT_SCOPE` (403), the user's API key lacks the required permission.
Tell them which scope is needed (see SKILL.md § API Scopes Reference) and direct them to `https://recite.rivra.dev/settings/api`.

---

## 📊 Output Schema

The CSV ledger uses a **dynamic schema** — columns are determined by what the Recite API returns plus four fixed fields:

| Column | Source |
|--------|--------|
| `scan_id` | API response |
| `transaction_type` | API response |
| `OriginalFilename` | Added by the skill |
| `NewFilename` | Added by the skill |
| *(all other columns)* | Flattened from `extracted_data` |

New API fields are automatically added as new columns without rewriting existing data.

---

## 📋 Full Subcommand List

```
scan-dir            Scan folder → rename + CSV (bookkeeping workflow)
scan                Single file scan → JSON
scan-text           Scan from plain text file or stdin → JSON
get-scan            Retrieve scan by ID → JSON
batch               Submit async batch (max 20 files) → JSON
batch-status        Check batch job status → JSON
batch-results       Get completed batch results → JSON
batch-wait          Submit batch + poll until done → JSON
transactions        List/filter transactions → JSON
transaction-get     Get single transaction → JSON
transaction-create  Create transaction manually → JSON
transaction-update  Update transaction fields → JSON
transaction-delete  Delete transaction → JSON
import              Bulk import from JSON file (max 500) → JSON
summary             Financial analytics / aggregates → JSON
projects            List projects → JSON
project-create      Create project → JSON
project-update      Update project → JSON
project-delete      Delete project → JSON
categories          List categories → JSON
category-add        Add custom category → JSON
category-delete     Remove custom category → JSON
vendors             List vendors → JSON
vendor-add          Add vendor with default category → JSON
vendor-delete       Remove vendor → JSON
rules               List automation rules → JSON
rule-create         Create automation rule → JSON
rule-update         Update rule → JSON
rule-delete         Delete rule → JSON
webhooks            List webhooks → JSON
webhook-create      Register webhook endpoint → JSON
webhook-delete      Unregister webhook → JSON
export              Export transactions as CSV/JSON → JSON or file
usage               View API quota and request metrics → JSON
```

---

*Optimized for Claude Sonnet 4.6 / Opus 4.6 Agentic Workflows.*
