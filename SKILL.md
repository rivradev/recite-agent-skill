name: recite
description: AI receipt scanner & full bookkeeping automation. Scan receipts, manage transactions, run financial analytics, configure automation rules, and export data — all via the Recite API. Supports batch processing, project organization, category/vendor management, and webhook automation.
---

# Recite 🦞🤵

Full-featured bookkeeping automation powered by the [Recite Vision API](https://recite.rivra.dev/docs/api).
Scan receipts, manage transactions, analyze spending, and automate categorization — all from a single CLI.

---

## Setup

### 1. API Key

Generate a key at `https://recite.rivra.dev/settings/api`, then configure it one of two ways:

```bash
# Option A — environment variable
export RECITE_API_KEY="re_live_YOUR_KEY"

# Option B — config file
mkdir -p ~/.config/recite
echo '{"api_key": "re_live_YOUR_KEY"}' > ~/.config/recite/config.json
```

### 2. Dependencies

```bash
pip install requests
```

### 3. Files

| File | Purpose |
|------|---------|
| `process_receipts.py` | Main CLI — all subcommands |
| `recite_client.py` | API client module (imported by the CLI) |
| `long_term_memory.md` | Persistent agent instructions |
| `bookkeeping_transactions.CSV` | Generated ledger (in your target folder) |

---

## Operational Rules

### 1. Mandatory API Key Pre-check

Before any scanning or data operation, verify a Recite API key is available. If missing, stop and instruct the user to generate one at `https://recite.rivra.dev/settings/api`. Do not proceed without a key.

### 2. Check API Quota Before Bulk Operations

Run `usage` before batch-scanning large directories to confirm sufficient quota remains.

### 3. Prefer `scan-dir` for Routine Bookkeeping

`scan-dir` handles the complete workflow: scan → rename → deduplicate → append to CSV. Use individual `scan`, `batch`, or `transaction-create` commands only when finer control is needed.

### 4. Use Batch for Large Sets

For more than 5 files, prefer `batch` + `batch-wait` over sequential `scan` calls to stay within rate limits (100 req/min).

### 5. Duplicate Prevention

`scan-dir` tracks processed files by `OriginalFilename` in the CSV ledger. Re-running against the same directory is safe — already-recorded files are skipped automatically.

### 6. Schema-Aware CSV

The CSV ledger auto-expands when the API returns new fields. Existing rows are never overwritten; the expansion uses an atomic write (temp file + replace) to prevent data loss.

### 7. Apply Long-Term Memory Rules

`scan-dir` prints `long_term_memory.md` to stdout at startup. Always read and apply those rules before acting on the output (e.g., custom categorization, amount alerts, file-move instructions).

---

## CLI Reference

All subcommands except `scan-dir` print JSON to stdout.

```
python process_receipts.py <subcommand> [options]
python process_receipts.py <subcommand> --help
```

Backward-compatible: `python process_receipts.py <directory>` still triggers `scan-dir`.

---

### Receipt Scanning

```bash
# Scan an entire folder (original bookkeeping workflow)
python process_receipts.py scan-dir ./receipts/ skills/recite/
python process_receipts.py scan-dir ./receipts/ skills/recite/ --project-id proj_abc

# Scan a single file → JSON
python process_receipts.py scan receipt.jpg
python process_receipts.py scan invoice.pdf --project-id proj_abc

# Scan from plain text (e.g. email body copy-pasted to a file)
python process_receipts.py scan-text receipt.txt
echo "Starbucks $5.40 2026-03-20" | python process_receipts.py scan-text -

# Retrieve a previous scan result
python process_receipts.py get-scan scan_abc123
```

### Batch Scanning (Async)

```bash
# Submit up to 20 files for async processing
python process_receipts.py batch img1.jpg img2.png invoice.pdf

# Check status (pending | processing | completed | failed)
python process_receipts.py batch-status batch_xyz

# Retrieve results once completed
python process_receipts.py batch-results batch_xyz

# Convenience: submit + wait + print results in one call
python process_receipts.py batch-wait batch_xyz --timeout 120 --interval 5
```

### Transactions

```bash
# List with filters
python process_receipts.py transactions
python process_receipts.py transactions --start-date 2026-01-01 --end-date 2026-03-31
python process_receipts.py transactions --category Travel --limit 50 --sort -date
python process_receipts.py transactions --vendor Starbucks --project-id proj_abc

# Get single transaction
python process_receipts.py transaction-get tx_abc123

# Create manually
python process_receipts.py transaction-create \
  --vendor "Acme Corp" --total 299.99 --date 2026-03-20 \
  --category "Software" --notes "Annual license"

# Update fields
python process_receipts.py transaction-update tx_abc123 category=Travel notes="Q1 conf"

# Delete (requires transactions:delete scope)
python process_receipts.py transaction-delete tx_abc123
```

### Bulk Import

```bash
# Import up to 500 transactions from a JSON file
python process_receipts.py import transactions.json
```

The JSON file must be a list `[{...}, ...]` or `{"transactions": [{...}, ...]}`. Each object should include at minimum `vendor`, `total`, and `date`.

### Financial Summary & Analytics

```bash
# Overall summary
python process_receipts.py summary

# Date-ranged summary
python process_receipts.py summary --start-date 2026-01-01 --end-date 2026-03-31

# Grouped breakdowns
python process_receipts.py summary --group-by category
python process_receipts.py summary --group-by vendor
python process_receipts.py summary --group-by month --project-id proj_abc
```

### Export

```bash
# Export as CSV (default)
python process_receipts.py export
python process_receipts.py export --format csv --start-date 2026-01-01 -o q1.csv

# Export as JSON
python process_receipts.py export --format json --category Travel -o travel.json
```

### Projects

```bash
python process_receipts.py projects
python process_receipts.py project-create "Q1 2026" --description "First quarter expenses"
python process_receipts.py project-update proj_abc name="Q1 2026 Final"
python process_receipts.py project-delete proj_abc
```

### Categories

```bash
python process_receipts.py categories
python process_receipts.py category-add "SaaS Tools" --description "Cloud subscriptions" --color "#4A90E2"
python process_receipts.py category-delete "SaaS Tools"
```

### Vendors

```bash
python process_receipts.py vendors
python process_receipts.py vendor-add "AWS" --category "Infrastructure"
python process_receipts.py vendor-add "Starbucks" --category "Meals & Entertainment"
python process_receipts.py vendor-delete "Starbucks"
```

### Automation Rules

Rules auto-apply during scanning. Evaluated in priority order (highest first).

```bash
# List rules
python process_receipts.py rules

# Create a vendor→category rule
python process_receipts.py rule-create \
  --type vendor_category \
  --condition '{"vendor_contains": "Amazon"}' \
  --action '{"set_category": "Software Services"}' \
  --priority 10

# Create a transaction rule (e.g. flag large expenses)
python process_receipts.py rule-create \
  --type transaction_rule \
  --condition '{"total_gte": 500}' \
  --action '{"add_tag": "review_required"}' \
  --priority 5

# Update / disable a rule
python process_receipts.py rule-update rule_abc enabled=false priority=1

# Delete a rule
python process_receipts.py rule-delete rule_abc
```

### Webhooks

```bash
# List webhooks
python process_receipts.py webhooks

# Register a webhook
python process_receipts.py webhook-create \
  https://your-app.example.com/webhooks/recite \
  transaction.created transaction.updated batch.completed \
  --secret "your_hmac_secret"

# Unregister
python process_receipts.py webhook-delete wh_abc123
```

Valid events: `transaction.created`, `transaction.updated`, `transaction.deleted`, `batch.completed`.
Deliveries include `X-Recite-Signature` (HMAC-SHA256) when a secret is configured.

### Usage & Quota

```bash
python process_receipts.py usage
```

Returns remaining scan quota, daily/hourly request counts, and plan limits.

---

## Long-Term Memory & Custom Logic

Edit `long_term_memory.md` to add persistent rules for the agent. The script prints this file to stdout on every `scan-dir` run — the calling agent should read and apply the rules.

**Examples:**
```markdown
- Always categorize 'Amazon' as 'Software Services'.
- Alert me if any single receipt exceeds $500.
- After scanning, move all files to a sub-folder named processed/.
- Default currency is GBP for receipts from UK vendors.
```

---

## API Scopes Reference

Some operations require elevated scopes. Check your key's permissions at `https://recite.rivra.dev/settings/api`.

| Operation | Required Scope |
|-----------|---------------|
| Scan receipts | `scan:create` |
| Read scans | `scan:read` |
| List/read transactions | `transactions:read` |
| Create transactions | `transactions:create` |
| Update transactions | `transactions:update` |
| Delete transactions | `transactions:delete` |
| Batch scanning | `batch:create`, `batch:read` |
| Manage projects | `projects:write` |
| Export data | `export:create` |
| Manage webhooks | `webhooks:manage` |
| Read/write rules | `rules:read`, `rules:write` |
| View usage | `usage:read` |

---

## Error Handling

All errors from API subcommands are printed as structured JSON:

```json
{
  "success": false,
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Daily scan quota exceeded.",
    "details": {}
  },
  "http_status": 429
}
```

Common codes: `INVALID_API_KEY` (401), `INSUFFICIENT_SCOPE` (403), `NOT_FOUND` (404),
`RATE_LIMITED` / `QUOTA_EXCEEDED` (429), `EXTRACTION_FAILED` (422).

---

## Strategic Moat

- **Agent-First JSON Output** — every subcommand returns structured JSON for downstream automation.
- **Atomic CSV Writes** — schema expansion never corrupts existing data.
- **Full API Coverage** — scanning, batch, transactions, analytics, rules, webhooks, export.
- **Backward Compatible** — existing `scan-dir` workflows require zero changes.
