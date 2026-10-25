# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from app.config import DEFAULT_ALLOWED_HOSTS
from app.urls import (
    BROWSER_HEADERS,
    HONEST_HEADERS,
    UrlError,
    extract_url,
    needs_resolving,
    normalise,
    platform_of,
    resolve_headers,
    resolve_redirects,
    target_from_shared,
)


def target(*fields):
    return target_from_shared(*fields, allowed_hosts=DEFAULT_ALLOWED_HOSTS, resolve=False)


def test_instagram_share_text_with_tracking():
    t = target(None, "Look at this! https://www.instagram.com/p/DPq1aBcXyZ_/?igsh=MWx0eGl5 nice")
    assert t.url == "https://www.instagram.com/p/DPq1aBcXyZ_/"
    assert (t.platform, t.kind, t.key) == ("instagram", "post", "DPq1aBcXyZ_")


def test_instagram_username_prefixed_post():
    t = target("https://www.instagram.com/examplecreator/p/DPq1aBcXyZ_/")
    assert t.url == "https://www.instagram.com/p/DPq1aBcXyZ_/"


@pytest.mark.parametrize("path", ["reel", "reels"])
def test_instagram_reel(path):
    t = target(f"https://instagram.com/{path}/Cabc-123/?utm_source=ig_web_copy_link")
    assert t.url == "https://www.instagram.com/reel/Cabc-123/"
    assert t.kind == "reel"


def test_instagram_story():
    t = target("https://www.instagram.com/stories/someone/3456789012345678901/?igsh=x")
    assert t.url == "https://www.instagram.com/stories/someone/3456789012345678901/"
    assert t.kind == "story"


def test_instagram_profile_rejected():
    with pytest.raises(UrlError) as exc:
        target("https://www.instagram.com/examplecreator/")
    assert exc.value.code == "unsupported_link"


def test_foreign_host_rejected():
    with pytest.raises(UrlError) as exc:
        target("https://evil.example/https://www.instagram.com/p/abc/")
    assert exc.value.code == "host_not_allowed"


def test_lookalike_host_rejected():
    with pytest.raises(UrlError) as exc:
        target("https://instagram.com.evil.example/p/abc/")
    assert exc.value.code == "host_not_allowed"


@pytest.mark.parametrize(
    ("host", "platform"),
    [
        ("instagram.com", "instagram"),
        ("www.instagram.com", "instagram"),
        ("m.instagram.com", "instagram"),
        ("instagr.am", "instagram"),
        ("facebook.com", "facebook"),
        ("web.facebook.com", "facebook"),
        ("fb.watch", "facebook"),
        ("evilinstagram.com", "other"),
        ("notfacebook.com", "other"),
        ("instagram.com.evil.example", "other"),
        ("facebook.com.evil.example", "other"),
    ],
)
def test_platform_is_the_domain_or_a_subdomain_only(host, platform):
    assert platform_of(host) == platform


def test_lookalike_host_is_no_platform_even_on_the_allowlist():
    hosts = (*DEFAULT_ALLOWED_HOSTS, "evilinstagram.com", "evilfacebook.com")
    for url in ("https://evilinstagram.com/p/abc/", "https://evilfacebook.com/reel/123/"):
        with pytest.raises(UrlError) as exc:
            normalise(url, hosts)
        assert exc.value.code == "host_not_allowed"
    assert not needs_resolving("https://evilfacebook.com/share/r/abc/")


def test_internal_address_rejected():
    with pytest.raises(UrlError):
        target("http://169.254.169.254/latest/meta-data/")


def test_facebook_tracking_stripped_and_host_normalised():
    t = target("https://m.facebook.com/watch/?v=123456789&mibextid=abc&rdid=xyz")
    assert t.url == "https://www.facebook.com/watch/?v=123456789"
    assert (t.platform, t.kind, t.key) == ("facebook", "reel", "123456789")


def test_facebook_reel_path():
    t = target("https://www.facebook.com/reel/987654321/?s=fb_shorts")
    assert t.url == "https://www.facebook.com/reel/987654321/"
    assert t.key == "987654321"


def test_no_url():
    with pytest.raises(UrlError) as exc:
        extract_url("just some text", None, "")
    assert exc.value.code == "no_url"


def test_trailing_punctuation_removed():
    assert extract_url("see (https://www.instagram.com/p/abc/).") == "https://www.instagram.com/p/abc/"


def test_first_field_with_url_wins():
    t = target("https://www.instagram.com/p/AAA/", "https://www.instagram.com/p/BBB/")
    assert t.key == "AAA"


def test_normalise_requires_allowlist():
    with pytest.raises(UrlError):
        normalise("https://www.instagram.com/p/abc/", allowed_hosts=("facebook.com",))


def facebook(request: httpx.Request) -> httpx.Response:
    """Answers like facebook.com did on 2026-10-19: a share link gets 400 for a request that
    looks like an incomplete browser and a redirect to the reel for any other client."""
    if request.url.path.startswith("/share/r/"):
        if "Chrome" in request.headers.get("user-agent", ""):
            return httpx.Response(400)
        return httpx.Response(302, headers={"location": "https://www.facebook.com/reel/954162721072206"})
    return httpx.Response(200)


def test_facebook_share_link_resolves_to_the_reel():
    url = "https://www.facebook.com/share/r/1FHoovVN4K/"
    assert needs_resolving(url)
    resolved = resolve_redirects(url, DEFAULT_ALLOWED_HOSTS, transport=httpx.MockTransport(facebook))
    assert resolved == "https://www.facebook.com/reel/954162721072206"
    t = normalise(resolved, DEFAULT_ALLOWED_HOSTS)
    assert (t.platform, t.kind, t.key) == ("facebook", "reel", "954162721072206")


def test_facebook_gets_an_honest_user_agent_instagram_keeps_the_browser_one():
    assert resolve_headers("https://www.facebook.com/share/v/abc/") == HONEST_HEADERS
    assert resolve_headers("https://fb.watch/abc/") == HONEST_HEADERS
    assert resolve_headers("https://www.instagram.com/share/abc/") == BROWSER_HEADERS
    assert HONEST_HEADERS["User-Agent"].startswith("Sharewerk/")


def test_resolver_stops_before_login_pages_and_foreign_hosts():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/share/r/login/":
            return httpx.Response(302, headers={"location": "https://www.facebook.com/login/?next=x"})
        if request.url.path == "/share/r/away/":
            return httpx.Response(302, headers={"location": "https://evil.example/steal"})
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    for url in ("https://www.facebook.com/share/r/login/", "https://www.facebook.com/share/r/away/"):
        assert resolve_redirects(url, DEFAULT_ALLOWED_HOSTS, transport=transport) == url
