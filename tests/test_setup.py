# SPDX-License-Identifier: Apache-2.0
"""setup.sh writes .env for one of the two ways to run Sharewerk (own domain with Caddy, or at home
with Tailscale). Starting the containers is tested in CI (.github/workflows/test.yml)."""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(SH is None, reason="no POSIX shell")


@pytest.fixture
def repo(tmp_path) -> Path:
    for name in ("setup.sh", ".env.example"):
        shutil.copy(ROOT / name, tmp_path / name)
    return tmp_path


def setup(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([SH, str(repo / "setup.sh"), *args, "--no-start"], capture_output=True, text=True, timeout=30)


def env(repo: Path) -> dict[str, str]:
    values = {}
    for line in (repo / ".env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            assert name not in values, f"{name} twice in .env"
            values[name] = value
    return values


def test_own_domain(repo):
    r = setup(repo, "--domain", "sharewerk.example.com")
    assert r.returncode == 0, r.stderr
    values = env(repo)
    assert re.fullmatch(r"[0-9a-f]{64}", values["SHAREWERK_AUTH_TOKEN"])
    assert values["SHAREWERK_AUTH_MODE"] == "token"
    assert values["SHAREWERK_DOMAIN"] == "sharewerk.example.com"
    assert values["COMPOSE_FILE"] == "compose.yaml:compose.caddy.yaml"
    assert (repo / "secrets").is_dir()
    if os.name == "posix":
        assert stat.S_IMODE((repo / ".env").stat().st_mode) == 0o600
    # Everything else of .env.example is still there.
    assert values["SHAREWERK_INSTAGRAM_PAUSE"] == "20"


def test_tailscale(repo):
    r = setup(repo, "--tailscale", "tskey-auth-kExample123-ABCdef")
    assert r.returncode == 0, r.stderr
    values = env(repo)
    assert values["TS_AUTHKEY"] == "tskey-auth-kExample123-ABCdef"
    assert values["COMPOSE_FILE"] == "compose.yaml:compose.tailscale.yaml"


def test_running_again_keeps_the_token_and_switches_the_way(repo):
    setup(repo, "--domain", "sharewerk.example.com")
    token = env(repo)["SHAREWERK_AUTH_TOKEN"]
    assert setup(repo, "--tailscale", "tskey-auth-kExample123").returncode == 0
    values = env(repo)
    assert values["SHAREWERK_AUTH_TOKEN"] == token
    assert values["COMPOSE_FILE"] == "compose.yaml:compose.tailscale.yaml"


def test_a_token_set_by_hand_stays(repo):
    text = (repo / ".env.example").read_text(encoding="utf-8")
    (repo / ".env").write_text(text.replace("SHAREWERK_AUTH_TOKEN=\n", "SHAREWERK_AUTH_TOKEN=" + "a" * 40 + "\n"))
    assert setup(repo, "--domain", "sharewerk.example.com").returncode == 0
    assert env(repo)["SHAREWERK_AUTH_TOKEN"] == "a" * 40


@pytest.mark.parametrize("args", [
    ["--domain", "evil.com;rm -rf /"],
    ["--domain", "sharewerk.example.com\nSHAREWERK_AUTH_MODE=none"],
    ["--domain", "localhost"],
    ["--domain", "-x.example.com"],
    ["--domain", "https://sharewerk.example.com"],
    ["--tailscale", "not-a-key"],
    ["--tailscale", "tskey-auth-x$(id)"],
    ["--domain"],
    ["--unknown"],
])
def test_unusable_input_changes_nothing(repo, args):
    r = setup(repo, *args)
    assert r.returncode != 0
    assert not (repo / ".env").exists()
