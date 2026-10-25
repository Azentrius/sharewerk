# SPDX-License-Identifier: Apache-2.0
"""Cookies per platform: what the browser extension sends, and what each download gets.

The extension sends the cookies of one platform after you log in there. They are kept in
DATA_DIR/cookies/<platform>.txt (Netscape format, mode 600). A download gets only the cookies of
its own platform: the sent ones if there are any, otherwise the lines for that platform from
SHAREWERK_COOKIES_FILE (the file put in place by hand).

Cookie values are never logged and never part of an error message.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)

HEADER = "# Netscape HTTP Cookie File"
MAX_COOKIES = 100
MAX_LENGTH = 4096  # per field; browsers keep a cookie below 4 KB
LATEST = 253402300799  # 9999-12-31, the latest expiry date that makes sense


@dataclass(frozen=True)
class Platform:
    domain: str  # the cookies must belong to this domain or one of its subdomains
    session: tuple[str, ...]  # cookies that exist only while an account is logged in


# The names are the platforms of app/urls.py. A new platform needs an entry here and in the
# extension (extension/sync.js), and its hosts in the allowlist.
PLATFORMS = {
    "instagram": Platform("instagram.com", ("sessionid",)),
    "facebook": Platform("facebook.com", ("c_user", "xs")),
}


class CookieError(ValueError):
    """Sent cookies that cannot be used. `code` is a stable identifier for the extension."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def belongs(domain: str, base: str) -> bool:
    domain = domain.lower().lstrip(".")
    return domain == base or domain.endswith("." + base)


def _clean(value: object) -> bool:
    """A string that fits into one field of a cookies.txt line: printable ASCII only. A tab, a
    line break (also U+2028 and the like) or another control character would start a new field
    or line."""
    return isinstance(value, str) and len(value) <= MAX_LENGTH and all(" " <= c <= "~" for c in value)


def _expires(value: object) -> int:
    """Unix time of a cookie's end, 0 for a session cookie. Raises CookieError for anything else."""
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CookieError("cookies_invalid", "a cookie has an unusable expiry date")
    if not 0 <= value <= LATEST:
        raise CookieError("cookies_invalid", "a cookie has an unusable expiry date")
    return int(value)


def netscape(platform: str, cookies: object) -> str:
    """The cookies of `platform` as a cookies.txt, as the browser extension sends them (the fields
    of chrome.cookies.Cookie). Raises CookieError if one belongs to another site, if a field could
    break the file, or if the login cookies are missing (the account is logged out)."""
    spec = PLATFORMS[platform]
    if not isinstance(cookies, list) or not cookies or len(cookies) > MAX_COOKIES:
        raise CookieError("cookies_invalid", f"expected a list of 1 to {MAX_COOKIES} cookies")
    lines = [HEADER, f"# {platform}, sent by the Sharewerk browser extension"]
    names = set()
    for cookie in cookies:
        if not isinstance(cookie, dict):
            raise CookieError("cookies_invalid", "every cookie must be an object")
        domain, name, value = cookie.get("domain"), cookie.get("name"), cookie.get("value")
        path = cookie.get("path") or "/"
        if not all(_clean(v) for v in (domain, name, value, path)) or not name or not domain:
            raise CookieError("cookies_invalid", "a cookie has a missing or unusable field")
        if not belongs(domain, spec.domain):
            raise CookieError("cookie_domain", f"a cookie of {domain} does not belong to {spec.domain}")
        expires = _expires(cookie.get("expirationDate"))
        if cookie.get("hostOnly"):
            domain, subdomains = domain.lstrip("."), "FALSE"
        else:
            domain, subdomains = "." + domain.lstrip("."), "TRUE"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        lines.append("\t".join((domain, subdomains, path, secure, str(expires), name, value)))
        names.add(name)
    missing = [n for n in spec.session if n not in names]
    if missing:
        raise CookieError("cookie_session_missing", f"not logged in: {', '.join(missing)} missing")
    return "\n".join(lines) + "\n"


def sent_file(settings: Settings, platform: str) -> Path:
    return settings.cookies_dir / f"{platform}.txt"


def save(settings: Settings, platform: str, text: str) -> None:
    """Replace the sent cookies of `platform`; readable by the app's user only. Raises OSError."""
    directory = settings.cookies_dir
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = directory / f".{platform}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, sent_file(settings, platform))
    finally:
        tmp.unlink(missing_ok=True)


def remove(settings: Settings, platform: str) -> bool:
    """Delete the sent cookies of `platform`. False if there were none. Raises OSError."""
    try:
        sent_file(settings, platform).unlink()
    except FileNotFoundError:
        return False
    return True


def _lines_for(path: Path, platform: str) -> list[str]:
    """The cookie lines of `platform` in a cookies.txt; [] if it cannot be read."""
    base = PLATFORMS[platform].domain
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _warn_unreadable(path, exc)
        return []
    found = []
    for line in text.split("\n"):  # not splitlines(): that also splits at U+2028 and the like
        line = line.removesuffix("\r")
        domain = line.removeprefix("#HttpOnly_").split("\t", 1)[0]
        if line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        if line.count("\t") == 6 and belongs(domain, base):
            found.append(line)
    return found


_warned: set[tuple[str, float]] = set()


def _warn_unreadable(path: Path, exc: Exception) -> None:
    """Say once per version of the file that it exists but cannot be used (the health check reads
    it every minute). Only the kind of error: the message could quote the file."""
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        key = (str(path), 0.0)
    if key not in _warned:
        _warned.add(key)
        log.warning("cannot read the cookie file %s (%s); downloads run without its cookies", path, type(exc).__name__)


def source(settings: Settings, platform: str) -> tuple[Path, str] | None:
    """Where the cookies of `platform` come from: the sent ones ("extension"), else the cookie file
    put in place by hand ("file") if it holds cookies of that platform, else None."""
    if platform not in PLATFORMS:
        return None
    sent = sent_file(settings, platform)
    if sent.is_file():
        return sent, "extension"
    if settings.cookies_file.is_file() and _lines_for(settings.cookies_file, platform):
        return settings.cookies_file, "file"
    return None


def for_download(settings: Settings, platform: str, dest: Path) -> Path | None:
    """Write the cookies of `platform` to `dest` (mode 600) for one download, or return None if
    there are none. A copy, because both tools write updated cookies back into the file they get."""
    found = source(settings, platform)
    if found is None:
        return None
    lines = _lines_for(found[0], platform)
    if not lines:
        return None
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join([HEADER, *lines]) + "\n")
    return dest
