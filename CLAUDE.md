# Claude Code Guide: Recite Agent Skill 🦞🤵

This guide helps **Claude Code** and other AI agents efficiently operate the Recite bookkeeping skill.

## 🚀 Core Commands

To process a directory of receipts:
```bash
python skills/recite/process_receipts.py <target_directory> skills/recite/
```
> On macOS/Linux you may need `python3` instead of `python`.

- `<target_directory>`: Folder containing images/PDFs.
- `skills/recite/`: The skill directory where `long_term_memory.md` is located.

## 🔑 Environment & Config
- **API Key:** Ensure `RECITE_API_KEY` is set in the environment or defined in `~/.config/recite/config.json`.
- **Validation:** Always verify the API key availability before execution.

## 🤖 Operation Guidelines (For Claude)

1. **Read LTM First:** Always read `long_term_memory.md` before processing. The script prints it to stdout at startup — review and apply those custom rules (e.g., categorization overrides, alerting thresholds). It contains user-specific preferences.
2. **Deterministic Bookkeeping:** The script appends to `bookkeeping_transactions.CSV` in the target directory. After execution, summarize the new entries for the user.
3. **Smart Renaming:** Files are renamed to `[YYYY-MM-DD]_[Vendor].[ext]`. If a name collision occurs, a timestamp suffix is appended (e.g., `2024-05-20_Starbucks_1716220800.jpg`). Files whose `OriginalFilename` is already in the CSV ledger are skipped on re-runs to prevent duplicate entries.
4. **Error Handling:** If the Vision API call fails, the file is skipped with a warning printed to stdout. No CSV entry is written for failed scans — the file can be retried on the next run.

## 📊 Output Schema
The local ledger uses a **dynamic schema** — columns are determined by what the Recite API returns plus four fixed fields: `scan_id`, `transaction_type`, `OriginalFilename`, `NewFilename`. New API fields are automatically added as new CSV columns without rewriting existing data (atomic write protects against data loss during schema expansion).

## 📁 Key Files
- `process_receipts.py`: The execution engine.
- `long_term_memory.md`: Persistent user rules (printed to stdout at startup).
- `bookkeeping_transactions.CSV`: The final financial record (generated in the target folder).

---
*Optimized for Claude Sonnet 4.6 / Opus 4.6 Agentic Workflows.*
