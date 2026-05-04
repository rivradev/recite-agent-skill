# CLI Commands Reference

All subcommands except `scan-dir` print JSON to stdout.

```
python process_receipts.py <subcommand> [options]
python process_receipts.py <subcommand> --help
```

Backward-compatible: `python process_receipts.py <directory>` still triggers `scan-dir`.

## Receipt Scanning

```bash
# Scan an entire folder (original bookkeeping workflow)
python process_receipts.py scan-dir ./receipts/ skills/recite/
python process_receipts.py scan-dir ./receipts/ skills/recite/ --project-id proj_abc --auto-create-transaction --confidence-threshold 0.8

# Scan a single file → JSON
python process_receipts.py scan receipt.jpg
python process_receipts.py scan invoice.pdf --project-id proj_abc --format json

# Scan a URL → JSON
python process_receipts.py scan-url https://example.com/receipt.jpg --auto-create-transaction

# Scan from plain text
python process_receipts.py scan-text receipt.txt
echo "Starbucks $5.40 2026-03-20" | python process_receipts.py scan-text -

# Retrieve a previous scan result
python process_receipts.py get-scan scan_abc123
```

## Batch Scanning (Async)

```bash
# Submit up to 20 files or URLs
python process_receipts.py batch img1.jpg https://example.com/receipt.png invoice.pdf

# Check status (pending | processing | completed | failed)
python process_receipts.py batch-status batch_xyz

# Retrieve results once completed
python process_receipts.py batch-results batch_xyz

# Convenience: submit + wait + print results in one call
python process_receipts.py batch-wait batch_xyz --timeout 120 --interval 5
```

## Transactions

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

# Delete
python process_receipts.py transaction-delete tx_abc123
```

## Bulk Import

```bash
# Import up to 500 transactions from a JSON or CSV file
python process_receipts.py import transactions.json
python process_receipts.py import transactions.csv
```

## Financial Summary & Analytics

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

## Export

```bash
# Export as CSV (default)
python process_receipts.py export
python process_receipts.py export --format csv --start-date 2026-01-01 -o q1.csv

# Export as JSON
python process_receipts.py export --format json --category Travel -o travel.json
```

## Projects

```bash
python process_receipts.py projects
python process_receipts.py project-create "Q1 2026" --description "First quarter expenses"
python process_receipts.py project-update proj_abc name="Q1 2026 Final"
python process_receipts.py project-delete proj_abc
```

## Categories

```bash
python process_receipts.py categories
python process_receipts.py category-add "SaaS Tools" --description "Cloud subscriptions" --color "#4A90E2"
python process_receipts.py category-delete "SaaS Tools"
```

## Vendors

```bash
python process_receipts.py vendors
python process_receipts.py vendor-add "AWS" --category "Infrastructure"
python process_receipts.py vendor-add "Starbucks" --category "Meals & Entertainment"
python process_receipts.py vendor-delete "Starbucks"
```

## Automation Rules

```bash
# List rules
python process_receipts.py rules

# Create a vendor→category rule
python process_receipts.py rule-create \
  --type vendor_category \
  --condition '{"vendor_contains": "Amazon"}' \
  --action '{"set_category": "Software Services"}' \
  --priority 10

# Create a transaction rule
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

## Webhooks

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

## Usage & Quota

```bash
python process_receipts.py usage
```

## Bank Statements & Reconciliation

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

# List bank transactions
python process_receipts.py bank-transactions
python process_receipts.py bank-transactions --statement-id bs_abc123 --limit 50

# Get a single bank transaction
python process_receipts.py bank-transaction-get bt_abc123

# Update fields
python process_receipts.py bank-transaction-update bt_abc123 notes="Cleared"

# Delete a bank transaction
python process_receipts.py bank-transaction-delete bt_abc123

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
