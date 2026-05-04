name: recite
description: AI receipt scanner & full bookkeeping automation. Scan receipts, manage transactions, run financial analytics, configure automation rules, and export data — all via the Recite API. Supports batch processing, project organization, category/vendor management, webhook automation, bank statement import, bank transaction management, and receipt-to-bank reconciliation.
---

# Recite 🦞🤵

Full-featured bookkeeping automation powered by the [Recite Vision API](https://recite.rivra.dev/docs/api).

This skill is compatible with all modern AI agents, including:
- **OpenClaw**
- **Claude Code**
- **Claude Cowork**
- **Codex**
- **Antigravity**

Scan receipts, manage transactions, analyze spending, and automate categorization — all from a single, fast-loading CLI (`process_receipts.py`).

---

## Skill Navigation (Index)

As an agent, you can start executing commands immediately or load additional documentation on demand if you need more details.

### 📚 Detailed Documentation

If you need detailed instructions, refer to these sub-documents:
- **Setup & Auth:** read `docs/SETUP.md` (How to configure the API key and dependencies)
- **Rules & Scopes:** read `docs/RULES.md` (Mandatory checks, rate limits, schema details, and API scopes)
- **Full CLI Reference:** read `docs/COMMANDS.md` (A complete list of all supported subcommands and options)

### 🚀 Quick Start / Core Commands

The main entry point is `process_receipts.py`. You can view all commands directly from the CLI:
```bash
python process_receipts.py --help
```

**Common Workflows:**

1. **Bookkeeping / Scan Directory (Original Workflow)**
   ```bash
   python process_receipts.py scan-dir <target_directory> skills/recite/
   ```
   *(Note: This is the only command that outputs human-readable text. All others output JSON).*

2. **Single File Scan**
   ```bash
   python process_receipts.py scan receipt.jpg
   ```

3. **Check Usage & Quotas**
   ```bash
   python process_receipts.py usage
   ```

4. **Analytics & Search**
   ```bash
   python process_receipts.py transactions --limit 50
   python process_receipts.py summary --group-by category
   ```

## Long-Term Memory & Custom Logic

`long_term_memory.md` is **git-ignored** — it lives only on each user's machine. A starter template is provided as `long_term_memory.example.md`.

Before running `scan-dir`, check if `long_term_memory.md` exists. If it does, `scan-dir` prints its contents to stdout — read and apply every rule before acting on the output. If it does not, copy `long_term_memory.example.md` to `long_term_memory.md` and inform the user.
