# Recite Agent Skill Installation Guide

This guide provides instructions on how to install and configure the Recite Agent Skill for various modern AI coding agents. The primary requirement is setting up the Recite Vision API key correctly.

## Setting Up the API Key

The Recite API key must be configured so that the agent can access it via the CLI (`process_receipts.py`).

1. **Get an API Key:** Generate a key at [https://recite.rivra.dev/settings/api](https://recite.rivra.dev/settings/api). There is a generous free tier (20 free scans) available with no credit card required.
2. **Configure the Key:** You can store the key in either (or both) of the following locations. The CLI will check the config file first, then the environment variable.

   *   **Config file (Primary):**
       ```bash
       mkdir -p ~/.config/recite
       echo '{"api_key": "re_live_YOUR_KEY"}' > ~/.config/recite/config.json
       ```

   *   **Environment variable (Fallback):**
       ```bash
       export RECITE_API_KEY="re_live_YOUR_KEY"
       ```
       *(Note: Add the export line to your `~/.bashrc` or `~/.zshrc` to make it persistent).*

## Installing the Skill by Agent

### 1. Codex

Codex parses the `SKILL.md` file directly. To install:
1. Ensure the `SKILL.md` file has valid YAML frontmatter (starting and ending with `---`).
2. Add the directory containing the skill to Codex.
3. Make sure the `RECITE_API_KEY` is set in the environment where Codex runs, or the config file exists at `~/.config/recite/config.json`.

### 2. Claude Code

Claude Code can utilize skills by providing the directory.
1. Ensure the dependencies (`requests`) are installed in your Python environment.
2. Verify the API key is accessible via the shell environment where you start Claude Code, or in the config file.

### 3. OpenClaw

OpenClaw can load the skill directory.
1. Verify the `RECITE_API_KEY` is configured.
2. The agent will read `README.md` and `SKILL.md` for context. Make sure `long_term_memory.md` is initialized if required by your use case.

### 4. Antigravity

Antigravity generally requires standard Python execution environments.
1. Install dependencies (`pip install requests`).
2. Configure the API Key either in `~/.config/recite/config.json` or by exporting `RECITE_API_KEY`.
3. The agent can invoke the `process_receipts.py` CLI directly.

## Verifying Setup

Once the API key is configured, you can verify it's working by checking the usage quota:

```bash
python process_receipts.py usage
```
This should return your current usage statistics in JSON format.
