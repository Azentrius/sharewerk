# SPDX-License-Identifier: Apache-2.0
"""Find, validate and normalise the post URL inside shared text.

Android apps share a post as free text ("Look at this! https://...?igsh=..."),
so the URL has to be dug out first. Only hosts on the allowlist are accepted:
the downloaders must never be pointed at arbitrary URLs, because that would let
anyone with access make the server fetch internal addresses (SSRF).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx

from . import __version__

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

IG_POST_RE = re.compile(r"^/(?:[A-Za-z0-9_.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)")
IG_STORY_RE = re.compile(r"^/stories/([A-Za-z0-9_.]+)/(\d+)")
IG_SHARE_RE = re.compile(r"^/share/")

FB_TRACKING_PARAMS = {
    "mibextid", "rdid", "share_url", "__cft__", "__tn__", "ref", "sfnsn",
    "fs", "s", "app", "_rdr", "paipv", "eav", "wtsid", "sharing_source",
}

FB_SHORT_HOSTS = {"fb.watch", "fb.com"}

# Headers for resolving share and short links. Facebook answers its share links
# (/share/r/..., /share/v/..., /share/p/...) with 400 to a request that looks like an
# incomplete browser, but redirects an honest client to the post itself (seen 2026-10).
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.8",
}
HONEST_HEADERS = {"User-Agent": f"Sharewerk/{__version__} (+https://github.com/Azentrius/sharewerk)"}


class UrlError(ValueError):
    """Raised with a stable error code the UI can translate."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class Target:
    url: str
    platform: str  # "instagram" | "facebook"
    kind: str  # "post" | "reel" | "story" | "other"
    key: str  # short identifier for file names


def extract_url(*candidates: str | None) -> str:
    """Return the first http(s) URL found in any of the shared fields."""
    for value in candidates:
        if not value:
            continue
        match = URL_RE.search(value)
        if match:
            return match.group(0).rstrip(").,;!?»”")
    raise UrlError("no_url", "No link found in the shared content.")


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_allowed(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and _host(url) in allowed_hosts


def _on_domain(host: str, domain: str) -> bool:
    """The domain itself or one of its subdomains, not a host that merely ends with its name
    (evilinstagram.com)."""
    return host == domain or host.endswith("." + domain)


def platform_of(host: str) -> str:
    if _on_domain(host, "instagram.com") or host == "instagr.am":
        return "instagram"
    if _on_domain(host, "facebook.com") or host in FB_SHORT_HOSTS:
        return "facebook"
    return "other"


def needs_resolving(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host in FB_SHORT_HOSTS or host == "instagr.am":
        return True
    return bool(IG_SHARE_RE.match(parts.path)) and platform_of(host) in {"instagram", "facebook"}


def resolve_headers(url: str) -> dict[str, str]:
    """Facebook gets an honest user agent, Instagram the browser-like one it always got."""
    return HONEST_HEADERS if platform_of(_host(url)) == "facebook" else BROWSER_HEADERS


def resolve_redirects(
    url: str,
    allowed_hosts: tuple[str, ...],
    max_hops: int = 5,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Follow redirects of short/share links by hand, re-checking every hop.

    Returns the original URL if resolution fails; the extractors may still
    cope with it. `transport` is only for tests.
    """
    current = url
    try:
        with httpx.Client(
            follow_redirects=False, timeout=10.0, headers=resolve_headers(url), transport=transport
        ) as client:
            for _ in range(max_hops):
                response = client.get(current)
                location = response.headers.get("location")
                if response.status_code not in {301, 302, 303, 307, 308} or not location:
                    return current
                nxt = urljoin(current, location)
                if not is_allowed(nxt, allowed_hosts):
                    return current
                path = urlsplit(nxt).path
                if path.startswith(("/login", "/accounts/login", "/checkpoint")):
                    return current
                current = nxt
    except httpx.HTTPError:
        return url
    return current


def normalise(url: str, allowed_hosts: tuple[str, ...]) -> Target:
    """Validate the URL and turn it into a canonical form for the downloaders."""
    if not is_allowed(url, allowed_hosts):
        raise UrlError("host_not_allowed", f"Host not allowed: {_host(url) or url}")

    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    platform = platform_of(host)

    if platform == "instagram":
        m = IG_POST_RE.match(parts.path)
        if m:
            kind_raw, code = m.group(1), m.group(2)
            kind = "post" if kind_raw == "p" else ("reel" if kind_raw.startswith("reel") else "post")
            segment = "reel" if kind == "reel" else ("tv" if kind_raw == "tv" else "p")
            canonical = f"https://www.instagram.com/{segment}/{code}/"
            return Target(canonical, "instagram", kind, code)
        m = IG_STORY_RE.match(parts.path)
        if m:
            user, story_id = m.groups()
            canonical = f"https://www.instagram.com/stories/{user}/{story_id}/"
            return Target(canonical, "instagram", "story", story_id)
        raise UrlError(
            "unsupported_link",
            "Only links to single Instagram posts, reels or stories are supported.",
        )

    if platform == "facebook":
        if host in {"m.facebook.com", "web.facebook.com", "facebook.com"}:
            host = "www.facebook.com"
        query = [(k, v) for k, v in parse_qsl(parts.query) if k not in FB_TRACKING_PARAMS]
        canonical = urlunsplit(("https", host, parts.path, urlencode(query), ""))
        kind = "reel" if "/reel" in parts.path or "/watch" in parts.path or "/videos/" in parts.path else "post"
        key = _facebook_key(parts.path, dict(query))
        return Target(canonical, "facebook", kind, key)

    raise UrlError("host_not_allowed", f"Host not allowed: {host}")


def _facebook_key(path: str, query: dict[str, str]) -> str:
    for name in ("v", "story_fbid", "fbid"):
        if query.get(name):
            return re.sub(r"[^A-Za-z0-9_-]", "", query[name])[:40] or "post"
    tail = [p for p in path.split("/") if p]
    if tail:
        return re.sub(r"[^A-Za-z0-9_-]", "", tail[-1])[:40] or "post"
    return "post"


def target_from_shared(
    *fields: str | None, allowed_hosts: tuple[str, ...], resolve: bool = True
) -> Target:
    url = extract_url(*fields)
    if not is_allowed(url, allowed_hosts):
        raise UrlError("host_not_allowed", f"Host not allowed: {_host(url) or url}")
    if resolve and needs_resolving(url):
        url = resolve_redirects(url, allowed_hosts)
    return normalise(url, allowed_hosts)
