import urllib.request
import urllib.error
import json
import os
import time

import requests

SAVE_PATH = "missions.json"
KEYS_PATH = "keys.json"
WEBHOOK_URLS = [os.getenv("DISCORD"), os.getenv("DISCORD2")]
url = "https://github.com/Piet2001/Inzetten/raw/refs/heads/main/complete.json"


def sort_keys_json(keys_path: str = KEYS_PATH) -> None:
    """Sort keys.json alphabetically by key and rewrite it in-place."""
    if not os.path.exists(keys_path):
        return

    with open(keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return

    sorted_data = dict(sorted(data.items(), key=lambda item: item[0].lower()))

    with open(keys_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

# Load key translations
key_labels = {}
if os.path.exists(KEYS_PATH):
    sort_keys_json(KEYS_PATH)
    with open(KEYS_PATH, "r", encoding="utf-8") as f:
        key_labels = json.load(f)

def translate_key(key):
    label = key_labels.get(key)
    if label:
        # Take the first variant (before the pipe) and strip whitespace
        return label.split("|")[0].strip()
    return key

def translate_value(val):
    """If value is a dict, translate its keys; otherwise return as-is."""
    if isinstance(val, dict):
        return {translate_key(k): v for k, v in val.items()}
    return val

def send_discord(title: str, description: str):
    """Post an embed message to all configured Discord webhooks."""
    if not WEBHOOK_URLS:
        return
    embed = {
        "title": title,
        "description": description,
    }
    webhookdata = {
        "username": "Mission Change Tracking",
        "embeds": [
            embed
        ],
    }

    headers = {
        "Content-Type": "application/json"
    }

    for webhook_url in WEBHOOK_URLS:
        result = requests.post(webhook_url, json=webhookdata, headers=headers)
        if 200 <= result.status_code < 300:
            print(f"Webhook sent {result.status_code} to {webhook_url}")
        else:
            print(f"Not sent with {result.status_code} to {webhook_url}, response:\n{result.json()}")



# Load existing data for comparison (if available)
old_by_id = {}
if os.path.exists(SAVE_PATH):
    with open(SAVE_PATH, "r", encoding="utf-8") as f:
        old_data = json.load(f)
    old_by_id = {item["id"]: item for item in old_data}

# Download new data
with urllib.request.urlopen(url) as response:
    data = json.loads(response.read().decode())

# Save new data
with open(SAVE_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Downloaded missions.json")

# Compare
if not old_by_id:
    print("No previous version found — skipping comparison.")
else:
    new_by_id = {item["id"]: item for item in data}

    added_ids = set(new_by_id) - set(old_by_id)
    removed_ids = set(old_by_id) - set(new_by_id)
    common_ids = set(old_by_id) & set(new_by_id)

    def sort_key(x):
        return (0, int(x)) if x.isdigit() else (1, x)

    changes_found = False

    for mission_id in sorted(added_ids, key=sort_key):
        msg = f"**[ADDED]** id={mission_id} — {new_by_id[mission_id].get('name', '')}"
        print(msg)
        send_discord(
            title=f"[ADDED] id={mission_id}",
            description=new_by_id[mission_id].get("name", ""),
        )
        time.sleep(5)
        changes_found = True

    for mission_id in sorted(removed_ids, key=sort_key):
        msg = f"**[REMOVED]** id={mission_id} — {old_by_id[mission_id].get('name', '')}"
        print(msg)
        send_discord(
            title=f"[REMOVED] id={mission_id}",
            description=old_by_id[mission_id].get("name", ""),
        )
        time.sleep(5)
        changes_found = True

    for mission_id in sorted(common_ids, key=sort_key):
        old = old_by_id[mission_id]
        new = new_by_id[mission_id]
        all_keys = set(old) | set(new)
        field_changes = []
        for key in sorted(all_keys):
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                label = translate_key(key)
                # Expand dict fields into per-subkey lines
                if isinstance(old_val, dict) or isinstance(new_val, dict):
                    old_dict = old_val if isinstance(old_val, dict) else {}
                    new_dict = new_val if isinstance(new_val, dict) else {}
                    sub_keys = sorted(set(old_dict) | set(new_dict))
                    sub_lines = []
                    for sk in sub_keys:
                        sv_old = old_dict.get(sk)
                        sv_new = new_dict.get(sk)
                        if sv_old != sv_new:
                            sk_label = translate_key(sk)
                            if sv_old is None:
                                sub_lines.append(f"[ADDED] {sv_new} {sk_label}\n")
                            elif sv_new is None:
                                sub_lines.append(f"[REMOVED] {sv_old} {sk_label}\n")
                            else:
                                sub_lines.append(f"[CHANGED] {sv_old} -> {sv_new} {sk_label}\n")
                    if sub_lines:
                        field_changes.append(f"  {label}: \n" + "".join(sub_lines))
                else:
                    field_changes.append(f"  {label}: {old_val!r} -> {new_val!r}\n")
        if field_changes:
            header = f"**[CHANGED]** id={mission_id} — {new.get('name', '')}:"
            body = "\n".join(field_changes)
            print(header)
            print(body)
            send_discord(
                title=f"[CHANGED] id={mission_id} — {new.get('name', '')}",
                description=body[:3800],
            )
            time.sleep(5)
            changes_found = True

    if not changes_found:
        print("No changes detected.")
