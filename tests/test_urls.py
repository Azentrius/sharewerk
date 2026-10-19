# SPDX-License-Identifier: Apache-2.0
import pytest

from app.config import DEFAULT_ALLOWED_HOSTS
from app.urls import UrlError, extract_url, normalise, target_from_shared


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
