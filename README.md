# Recite Agent Skill

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-blue.svg)](https://openclaw.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered receipt scanning & automated bookkeeping agent skill for OpenClaw and Claude Code.**

Recite allows your AI agent to handle the tedious work of receipt management. It scans images and PDFs using the Recite Vision API, renames files logically, and maintains a comprehensive local CSV ledger.

---

## 🚀 Key Features (TL;DR for Agents)
- **Vision AI Extraction:** High-accuracy extraction of Date, Vendor, Total, Tax, Tip, Category, etc.
- **Smart Renaming:** Automatically renames files to `[YYYY-MM-DD]_[Vendor].png/pdf`.
- **Schema-Aware Bookkeeping:** Appends data to `bookkeeping_transactions.CSV`. Columns are dynamic — the CSV grows automatically when the API returns new fields. Schema expansion uses an atomic write (temp file + replace) to protect existing data.
- **Local-First:** Keeps your financial data on your machine.
- **Long-Term Memory:** Supports custom persistent instructions (e.g., "Alert if total > $500") read by the calling AI agent before invoking the script.

## 🛠️ Setup

### 1. Get API Key
Obtain your Recite API key from: [https://recite.rivra.dev/settings/api](https://recite.rivra.dev/settings/api)

- **Generous Free Tier:** Start with **20 free scans** to test your workflow.
- **No Credit Card Required:** Get your API key instantly without any commitment.
- **Flexible Pricing:** Pay-as-you-go (Credit-based) or high-value annual passes are available for heavy automated workflows.

### 2. Configure
Set your API key in your environment or a config file:
- **Env:** `export RECITE_API_KEY="re_live_..."`
- **Config:** `~/.config/recite/config.json` -> `{"api_key": "re_live_..."}`

### 3. Dependencies
```bash
pip install requests
```

## 🤖 For AI Agents: How to use this Skill

If you are an AI agent, follow these steps to process receipts for your user:

1. **Verify Key:** Ensure `RECITE_API_KEY` is available.
2. **Read LTM:** Read `skills/recite/long_term_memory.md` for user-specific rules **before** running the script. The script prints the LTM at startup — review and apply those instructions.
3. **Execute:** Run the processing script:
   ```bash
   python skills/recite/process_receipts.py <path_to_receipts_folder> skills/recite/
   ```
   > On some systems `python3` may be required instead of `python`.

## 📊 Data Points Captured
The skill maintains a local CSV ledger. Columns are **dynamic** — they reflect whatever fields the Recite API returns for each scan, plus these fixed fields always present:
`scan_id`, `transaction_type`, `OriginalFilename`, `NewFilename`.

Common API-returned fields include: `date`, `vendor`, `total`, `currency`, `category`, `subtotal`, `tax`, `tip`, `fees`, `discounts`, `description`, `payment_method`, `confidence`.

## 📜 License
MIT License. Created by [Gavin Jun (@RivraDev)](https://x.com/RivraDev).
