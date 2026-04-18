# AGENTS.md

## Project

Recite agent skill — CLI tool that scans receipts via the Recite Vision API, renames files, and maintains a local CSV ledger. Two files, no build system.

## Commands

```bash
# Run the CLI
python process_receipts.py <subcommand> [options]

# Run tests (no config file — pytest auto-discovers tests/)
pytest

# Install the only runtime dependency
pip install requests
pip install pytest   # for tests
```

No lint, format, or typecheck steps exist in this repo.

## Architecture

- `process_receipts.py` — CLI entry point, all subcommands, CSV ledger logic. Do not call directly as a library.
- `recite_client.py` — API client (`ReciteClient`, `ReciteError`). Imported by the CLI.
- `long_term_memory.md` — Git-ignored persistent user rules. If missing, copy from `long_term_memory.example.md`.
- `bookkeeping_transactions.CSV` — Generated in the scanned directory (also git-ignored).

## Key Conventions

- **Backward compat:** `python process_receipts.py <directory>` auto-prepends `scan-dir` subcommand.
- **Output:** `scan-dir` prints human-readable text + LTM rules. All other subcommands print JSON to stdout.
- **Error JSON:** `{"success": false, "error": {"code": "...", "message": "..."}, "http_status": N}`.
- **CSV schema is dynamic** — new API fields auto-add columns via atomic write (temp file + `os.replace`). Existing rows are never modified.
- **Duplicate prevention:** `scan-dir` skips files whose `OriginalFilename` already exists in the CSV.
- **File renaming:** `[YYYY-MM-DD]_[SanitizedVendor].[ext]`, with timestamp suffix on collision.
- **Rate limit:** 100 req/min. For >5 files, use `batch` + `batch-wait` instead of sequential `scan` calls.

## API Key

Required before any operation. Two sources — **always keep both in sync**:

1. **Config file** `~/.config/recite/config.json` → `{"api_key": "re_live_..."}`
2. **Environment variable** `RECITE_API_KEY`

Before operations, verify both exist and match:
```bash
cat ~/.config/recite/config.json   # source 1
echo $RECITE_API_KEY               # source 2
```

**When setting, updating, or removing a key — always update BOTH sources.** See `SKILL.md` → *Setup § 1. API Key* for the full procedure (edge-case decision table, step-by-step update/removal instructions, verification checklist).

## Tests

Tests are in `tests/` using `pytest` with mocking (no real API calls). Test fixtures use a `.test_tmp/` directory at repo root for temp files. Tests import `process_receipts` as a module (requires cwd on `PYTHONPATH` — `pytest` handles this automatically).
