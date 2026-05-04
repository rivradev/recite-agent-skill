# Setup & Configuration

## 1. API Key

Generate a key at `https://recite.rivra.dev/settings/api`, then store it in **both** locations so the CLI works regardless of how it is invoked:

```bash
# 1. Config file (primary — checked first by the CLI)
mkdir -p ~/.config/recite
echo '{"api_key": "re_live_YOUR_KEY"}' > ~/.config/recite/config.json

# 2. Environment variable (fallback — checked second)
export RECITE_API_KEY="re_live_YOUR_KEY"
```

### Key Resolution Order

The CLI (`process_receipts.py`) resolves the API key at runtime in this order:

1. **Config file** — `~/.config/recite/config.json` → `{"api_key": "re_live_..."}`
2. **Environment variable** — `RECITE_API_KEY`

The first source that contains a value wins. If neither is set, the CLI exits with a JSON error.

### When Setting or Updating the API Key

**CRITICAL: Always update BOTH sources.** Updating only one causes the CLI to use a stale key in certain contexts.

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

### When the User Asks to "Remove" or "Delete" the Key

Remove from **both** sources:
1. Delete or clear the config file: `rm ~/.config/recite/config.json` (or set `{"api_key": ""}`).
2. Unset the env var: `unset RECITE_API_KEY` and remove the `export` line from the shell profile.

### Edge Cases

| Situation | Action |
|-----------|--------|
| Config file exists but env var is empty | CLI uses the config file. Still set the env var to match. |
| Env var is set but config file is missing | CLI uses the env var. Still create the config file to match. |
| Both exist but hold **different** keys | CLI uses the **config file** value (source 1). Overwrite whichever is stale so both match. |
| User provides a key interactively | Write to both sources immediately — do not store only in session memory. |

## 2. Dependencies

```bash
pip install requests
```
