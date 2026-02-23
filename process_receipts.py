import os
import json
import re
import base64
import requests
import csv
import sys
import glob
import tempfile
from datetime import datetime

# Configuration
BASE_URL = "https://recite.rivra.dev/apiV1/api/v1"
CONFIG_PATH = os.path.expanduser("~/.config/recite/config.json")
CSV_NAME = "bookkeeping_transactions.CSV"
LTM_FILE = "long_term_memory.md"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def get_api_key():
    config = load_config()
    if config and "api_key" in config:
        return config["api_key"]
    return os.environ.get("RECITE_API_KEY")

def read_ltm(skill_path):
    ltm_path = os.path.join(skill_path, LTM_FILE)
    if os.path.exists(ltm_path):
        with open(ltm_path, 'r') as f:
            return f.read()
    return ""

def get_processed_filenames(csv_path):
    """Return the set of original filenames already recorded in the CSV ledger."""
    if not os.path.exists(csv_path):
        return set()
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames and 'OriginalFilename' in reader.fieldnames:
                return {row['OriginalFilename'] for row in reader if row.get('OriginalFilename')}
    except Exception:
        pass
    return set()

def flatten_dict(d, parent_key='', sep='_'):
    """Helper to flatten nested dictionaries for CSV columns."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Serialize lists as JSON strings to keep CSV values parseable
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)

def scan_receipt(api_key, file_path):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    mime_type = "image/jpeg"
    if file_path.lower().endswith('.pdf'):
        mime_type = "application/pdf"
    elif file_path.lower().endswith('.png'):
        mime_type = "image/png"

    payload = {
        "image_base64": f"data:{mime_type};base64,{encoded_string}"
    }

    try:
        response = requests.post(f"{BASE_URL}/scan", headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error scanning {file_path}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Request failed for {file_path}: {e}")
        return None

def update_csv_schema_and_append(csv_path, new_row_dict):
    """
    Handles CSV schema evolution:
    1. If a field is missing from API but exists in CSV, it leaves it blank.
    2. If a new field exists in API but not in CSV, it adds a new column.

    Schema expansion uses an atomic write (temp file + os.replace) to prevent
    data loss if the process crashes mid-write.
    """
    file_exists = os.path.exists(csv_path)
    existing_data = []
    existing_headers = []

    if file_exists:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_headers = reader.fieldnames if reader.fieldnames else []
            existing_data = list(reader)

    # Detect new fields not in existing headers
    new_fields = [k for k in new_row_dict.keys() if k not in existing_headers]

    if new_fields:
        print(f"New fields detected: {new_fields}. Expanding CSV columns...")
        existing_headers = existing_headers + new_fields
        # Atomic rewrite: write to a temp file then atomically replace the original.
        # Prevents data loss if the process crashes during the write.
        csv_dir = os.path.dirname(csv_path) or '.'
        tmp_fd, tmp_path = tempfile.mkstemp(dir=csv_dir, suffix='.tmp')
        try:
            with os.fdopen(tmp_fd, 'w', newline='', encoding='utf-8') as tmp_f:
                writer = csv.DictWriter(tmp_f, fieldnames=existing_headers, restval='')
                writer.writeheader()
                writer.writerows(existing_data)
                writer.writerow(new_row_dict)
            os.replace(tmp_path, csv_path)
        except Exception:
            os.unlink(tmp_path)
            raise
    else:
        # Standard append if no schema change
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=existing_headers, restval='')
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_row_dict)

    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python process_receipts.py <directory_path> [skill_path]")
        sys.exit(1)

    target_dir = sys.argv[1]
    skill_path = sys.argv[2] if len(sys.argv) > 2 else "."

    # Load and display long-term memory so the calling agent can apply custom rules
    ltm_content = read_ltm(skill_path)
    if ltm_content:
        print("--- Long-Term Memory (Custom Rules) ---")
        print(ltm_content)
        print("---------------------------------------")

    api_key = get_api_key()
    if not api_key:
        print("Error: API Key not found.")
        sys.exit(1)

    # Supported extensions — include uppercase variants for Linux (case-sensitive glob)
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.pdf', '*.JPG', '*.JPEG', '*.PNG', '*.PDF']
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(target_dir, ext)))

    if not files:
        print(f"No receipt files found in {target_dir}")
        return

    processed_count = 0
    csv_path = os.path.join(target_dir, CSV_NAME)

    # Load already-processed filenames to prevent duplicate entries on re-runs
    already_processed = get_processed_filenames(csv_path)

    for file_path in files:
        if CSV_NAME in file_path:
            continue

        basename = os.path.basename(file_path)
        if basename in already_processed:
            print(f"Skipping {basename} (already in ledger).")
            continue

        print(f"Processing: {basename}...")
        result = scan_receipt(api_key, file_path)

        if result and result.get('success'):
            # Flatten API response for CSV
            raw_data = result.get('data', {})
            row_data = flatten_dict(raw_data.get('extracted_data', {}))
            row_data['scan_id'] = raw_data.get('scan_id')
            row_data['transaction_type'] = raw_data.get('transaction_type')

            # Build safe filename — strip all Windows-forbidden characters from vendor
            ext = os.path.splitext(file_path)[1]
            date = row_data.get('date', 'UnknownDate')
            vendor = re.sub(r'[<>:"/\\|?*]', '-', str(row_data.get('vendor', 'UnknownVendor')))
            new_name = f"{date}_{vendor}{ext}"
            new_path = os.path.join(target_dir, new_name)

            # Name collision check — loop until a unique path is found
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(file_path):
                base_ts = int(datetime.now().timestamp())
                counter = 0
                while True:
                    suffix = str(base_ts) if counter == 0 else f"{base_ts}_{counter}"
                    new_name = f"{date}_{vendor}_{suffix}{ext}"
                    new_path = os.path.join(target_dir, new_name)
                    if not os.path.exists(new_path) or os.path.abspath(new_path) == os.path.abspath(file_path):
                        break
                    counter += 1

            # Rename first — CSV must reflect actual filesystem state, not intended state
            actual_new_name = new_name
            try:
                os.rename(file_path, new_path)
            except Exception as e:
                print(f"Warning: Could not rename {basename}: {e}. Recording with original filename.")
                actual_new_name = basename

            # Prepare and persist row to CSV
            row_to_save = row_data.copy()
            row_to_save['OriginalFilename'] = basename
            row_to_save['NewFilename'] = actual_new_name

            if update_csv_schema_and_append(csv_path, row_to_save):
                print(f"Successfully processed: {actual_new_name}")
                processed_count += 1
            else:
                print(f"Failed to save record for {file_path}.")
        else:
            print(f"Skipping {basename} due to API error.")

    print(f"\nProcessing Complete: {processed_count} files processed.")
    print(f"Transaction data saved to: {csv_path}")

if __name__ == "__main__":
    main()
