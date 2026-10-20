# SPDX-License-Identifier: Apache-2.0
"""Stand-in for gallery-dl and yt-dlp in tests: a real subprocess with the same command line.

Called as `python fake_downloader.py <gallery-dl|yt-dlp> <arguments of the real tool>`. Like the real
tools it resolves relative paths against its own working directory, honours the item range and
writes small synthetic media files plus metadata. Environment variables per tool
(prefix FAKE_GALLERY_DL_ or FAKE_YT_DLP_):

  FILES   number of media files the post has (default 0)
  EXIT    exit status (default 0)
  STDERR  text written to stderr

FAKE_LOG, if set, is a file that gets one JSON line per call: tool, working directory, arguments,
and whether the cookies and config files given on the command line exist from there.
"""

import json
import os
import sys
from pathlib import Path


def option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


def main() -> int:
    tool, args = sys.argv[1], sys.argv[2:]
    prefix = "FAKE_" + tool.upper().replace("-", "_") + "_"
    files = int(os.environ.get(prefix + "FILES", "0"))
    status = int(os.environ.get(prefix + "EXIT", "0"))
    stderr = os.environ.get(prefix + "STDERR", "")

    cookies, config = option(args, "--cookies"), option(args, "--config")
    if os.environ.get("FAKE_LOG"):
        record = {
            "tool": tool,
            "cwd": os.getcwd(),
            "args": args,
            "cookies_found": bool(cookies) and Path(cookies).is_file(),
            "config_found": bool(config) and Path(config).is_file(),
        }
        with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")

    if tool == "gallery-dl":
        limit = int(option(args, "--range").split("-")[1])
        directory = Path(option(args, "--directory"))
        directory.mkdir(parents=True, exist_ok=True)
        for i in range(1, min(files, limit) + 1):
            (directory / f"post_{i}.jpg").write_bytes(b"synthetic image %d" % i)
            meta = {"num": i, "username": "examplecreator", "description": "Five tips"}
            (directory / f"post_{i}.jpg.json").write_text(json.dumps(meta), encoding="utf-8")
    else:
        limit = int(option(args, "--playlist-items").split(":")[1])
        template = option(args, "--output")
        for i in range(1, min(files, limit) + 1):
            name = template.replace("%(playlist_index&{:03d}_|)s", f"{i:03d}_").replace("%(id)s", f"clip{i}")
            path = Path(name.replace("%(ext)s", "mp4"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic video %d" % i)
            info = {"uploader_id": "examplecreator", "description": "Five tips"}
            Path(name.replace("%(ext)s", "info.json")).write_text(json.dumps(info), encoding="utf-8")

    sys.stderr.write(stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
