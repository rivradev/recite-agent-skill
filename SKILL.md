name: recite
description: AI receipt scanner & full bookkeeping automation. Scan receipts, manage transactions, run financial analytics, configure automation rules, and export data — all via the Recite API. Supports batch processing, project organization, category/vendor management, webhook automation, bank statement import, bank transaction management, and receipt-to-bank reconciliation.
---

# Recite 🦞🤵

Full-featured bookkeeping automation powered by the [Recite Vision API](https://recite.rivra.dev/docs/api).
Scan receipts, manage transactions, analyze spending, and automate categorization — all from a single CLI.

---

## Setup

### 1. API Key

Generate a key at `https://recite.rivra.dev/settings/api`, then store it in **both** locations so the CLI works regardless of how it is invoked:

```bash
# 1. Config file (primary — checked first by the CLI)
mkdir -p ~/.config/recite
echo '{"api_key": "re_live_YOUR_KEY"}' > ~/.config/recite/config.json

# 2. Environment variable (fallback — checked second)
export RECITE_API_KEY="re_live_YOUR_KEY"
```

#### Key Resolution Order

The CLI (`process_receipts.py`) resolves the API key at runtime in this order:

1. **Config file** — `~/.config/recite/config.json` → `{"api_key": "re_live_..."}`
2. **Environment variable** — `RECITE_API_KEY`

The first source that contains a value wins. If neither is set, the CLI exits with a JSON error.

#### When Setting or Updating the API Key

**CRITICAL: Always update BOTH sources.** Updating only one causes the CLI to use a stale key in certain contexts (e.g., shell scripts that don't inherit the env var, or agents that only read the config file).

Steps to set or rotate the key:

1. Write the new key to `~/.config/recite/config.json`:
   ```bash
   mkdir -p ~/.config/recite
   echo '{"api_key": "re_live_NEW_KEY"}' > ~/.config/recite/config.json
   ```
2. Set or update the environment variable in the current session AND in the user's shell profile:
   ```bash
   export RECITE_API_KEY="re_live_NEW_KEY"
   ```
   Also append the `export` line to the user's shell profile (`~/.bashrc`, `~/.zshrc`, or equivalent) so it persists across sessions.
3. Verify both sources contain the same key:
   ```bash
   cat ~/.config/recite/config.json   # should show the new key
   echo $RECITE_API_KEY               # should print the new key
   ```
4. Confirm the key works by running `usage`:
   ```bash
   python process_receipts.py usage
   ```

#### When the User Asks to "Remove" or "Delete" the Key

Remove from **both** sources:
1. Delete or clear the config file: `rm ~/.config/recite/config.json` (or set `{"api_key": ""}`).
2. Unset the env var: `unset RECITE_API_KEY` and remove the `export` line from the shell profile.

#### Edge Cases

| Situation | Action |
|-----------|--------|
| Config file exists but env var is empty | CLI uses the config file. Still set the env var to match. |
| Env var is set but config file is missing | CLI uses the env var. Still create the config file to match. |
| Both exist but hold **different** keys | CLI uses the **config file** value (source 1). Overwrite whichever is stale so both match. |
| User provides a key interactively | Write to both sources immediately — do not store only in session memory. |

### 2. Dependencies

```bash
pip install requests
```

### 3. Files

| File | Purpose |
|------|---------|
| `process_receipts.py` | Main CLI — all subcommands |
| `recite_client.py` | API client module (imported by the CLI) |
| `long_term_memory.md` | Persistent agent instructions (user-local, git-ignored) |
| `long_term_memory.example.md` | Template for the above — copy to `long_term_memory.md` to get started |
| `bookkeeping_transactions.CSV` | Generated ledger (in your target folder) |

---

## Operational Rules

### 1. Mandatory API Key Pre-check

Before any scanning or data operation, verify a Recite API key is available **from both sources**. If either source is missing or the values differ, fix it before proceeding.

**Verification checklist (run every time before operations):**

1. Read the config file: `cat ~/.config/recite/config.json`
2. Read the env var: `echo $RECITE_API_KEY`
3. Confirm both exist and contain the **same key value**.

If both are missing: stop and instruct the user to generate a key at `https://recite.rivra.dev/settings/api`, then store it in both locations per the Setup section above.

If only one source is set: populate the missing source with the same key value before continuing.

If both exist but differ: the config file value takes precedence at runtime. Update the stale source (usually the env var) to match, then continue.

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

Before running `scan-dir`, check whether `long_term_memory.md` exists in the skill folder.

- **If it exists:** `scan-dir` will print its contents to stdout — read and apply every rule before acting on the output (e.g., custom categorization, amount alerts, file-move instructions).
- **If it does not exist:** copy `long_term_memory.example.md` to `long_term_memory.md` (or create a blank one) and notify the user that no custom rules are active yet. The script runs normally regardless — a missing file produces no error.

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
python process_receipts.py scan-dir ./receipts/ skills/recite/ --project-id proj_abc --auto-create-transaction --confidence-threshold 0.8

# Scan a single file → JSON
python process_receipts.py scan receipt.jpg
python process_receipts.py scan invoice.pdf --project-id proj_abc --format json

# Scan a URL → JSON
python process_receipts.py scan-url https://example.com/receipt.jpg --auto-create-transaction

# Scan from plain text (e.g. email body copy-pasted to a file)
python process_receipts.py scan-text receipt.txt
echo "Starbucks $5.40 2026-03-20" | python process_receipts.py scan-text -

# Retrieve a previous scan result
python process_receipts.py get-scan scan_abc123
```

### Batch Scanning (Async)

```bash
# Submit up to 20 files or URLs for async processing
python process_receipts.py batch img1.jpg https://example.com/receipt.png invoice.pdf

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
# Import up to 500 transactions from a JSON or CSV file
python process_receipts.py import transactions.json
python process_receipts.py import transactions.csv
```

The JSON file must be a list `[{...}, ...]` or `{"transactions": [{...}, ...]}`. Each object should include at minimum `vendor`, `total`, and `date`.
For CSV, pass `--format csv` or use a file with a `.csv` extension. It must contain the columns `vendor`, `total`, and `date`.

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

### Bank Statements

```bash
# Upload a bank statement CSV
python process_receipts.py bank-statement-upload statement.csv

# List bank statements
python process_receipts.py bank-statements
python process_receipts.py bank-statements --limit 10 --offset 20

# Get a single bank statement
python process_receipts.py bank-statement-get bs_abc123

# Delete a bank statement
python process_receipts.py bank-statement-delete bs_abc123

# Export a bank statement to a local CSV file
python process_receipts.py bank-statement-export bs_abc123 -o bank_txns.csv
```

### Bank Transactions

```bash
# List bank transactions (optionally filter by statement)
python process_receipts.py bank-transactions
python process_receipts.py bank-transactions --statement-id bs_abc123 --limit 50

# Get a single bank transaction
python process_receipts.py bank-transaction-get bt_abc123

# Update fields
python process_receipts.py bank-transaction-update bt_abc123 notes="Cleared"

# Delete a bank transaction
python process_receipts.py bank-transaction-delete bt_abc123
```

### Reconciliation

```bash
# List reconciliation links
python process_receipts.py reconciliation-links --statement-id bs_abc123

# Manually link a receipt transaction to a bank transaction
python process_receipts.py reconciliation-link-create --transaction-id tx_abc --bank-transaction-id bt_xyz

# Update a reconciliation link
python process_receipts.py reconciliation-link-update rl_abc status=confirmed

# Delete a reconciliation link
python process_receipts.py reconciliation-link-delete rl_abc

# Auto-match transactions for a statement
python process_receipts.py reconciliation-auto-match bs_abc123

# View reconciliation summary
python process_receipts.py reconciliation-summary bs_abc123

# Export reconciliation data
python process_receipts.py reconciliation-export --statement-id bs_abc123 -o recon.csv
```

---

## Long-Term Memory & Custom Logic

`long_term_memory.md` is **git-ignored** — it lives only on each user's machine and is never overwritten by `git pull`. A starter template is provided as `long_term_memory.example.md`.

**First-time setup:**
```bash
cp long_term_memory.example.md long_term_memory.md
# then edit long_term_memory.md with your own rules
```

The script prints the file to stdout on every `scan-dir` run — the calling agent should read and apply the rules. If the file is absent the script runs normally (no error).

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
