# Claude Code Guide: Recite Agent Skill 🦞🤵

This guide helps **Claude Code** and other AI agents efficiently operate the Recite bookkeeping skill.

## 🚀 Core Commands

To process a directory of receipts:
```bash
python3 process_receipts.py <target_directory> .
```
- `<target_directory>`: Folder containing images/PDFs.
- `.`: The current directory where `long_term_memory.md` is located.

## 🔑 Environment & Config
- **API Key:** Ensure `RECITE_API_KEY` is set in the environment or defined in `~/.config/recite/config.json`.
- **Validation:** Always verify the API key availability before execution.

## 🤖 Operation Guidelines (For Claude)

1. **Read Memory First:** Always consult `long_term_memory.md` before processing. It contains user-specific categorization rules and automation preferences.
2. **Deterministic Bookkeeping:** The script appends to `bookkeeping_transactions.CSV` in the target directory. After execution, summarize the new entries for the user.
3. **Smart Renaming:** Files are renamed to `[YYYY-MM-DD]_[Vendor].[ext]`. If a file already exists, it will be skipped to prevent duplicates.
4. **Error Handling:** If the Vision API fails to extract a "Total" or "Date", the entry will be logged as "Manual Review Required" in the CSV.

## 📊 Output Schema
The local ledger uses a comprehensive 19-column schema (Date, Vendor, Total, Currency, Category, Tax, Tip, etc.).

## 📁 Key Files
- `process_receipts.py`: The execution engine.
- `long_term_memory.md`: Persistent user rules.
- `bookkeeping_transactions.CSV`: The final financial record (generated in the target folder).

---
*Optimized for Claude Sonnet 4.0 / Opus 4.5 Agentic Workflows.*
