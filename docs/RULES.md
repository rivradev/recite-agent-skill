# Operational Rules & API Scopes

## Operational Rules

### 1. Mandatory API Key Pre-check

Before any scanning or data operation, verify a Recite API key is available **from both sources**. If either source is missing or the values differ, fix it before proceeding.

**Verification checklist (run every time before operations):**

1. Read the config file: `cat ~/.config/recite/config.json`
2. Read the env var: `echo $RECITE_API_KEY`
3. Confirm both exist and contain the **same key value**.

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

Common codes: `INVALID_API_KEY` (401), `INSUFFICIENT_SCOPE` (403), `NOT_FOUND` (404), `RATE_LIMITED` / `QUOTA_EXCEEDED` (429), `EXTRACTION_FAILED` (422).
