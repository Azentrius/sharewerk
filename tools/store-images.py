#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render the images of the Chrome Web Store listing: three screenshots (1280 x 800) in English and
German, and the small promo tile (440 x 280), into docs/chrome-web-store/.

The extension is built with tools/build-extension.py and shown in a headless Chrome or Edge, with a
stand-in for the chrome APIs and example data (no real account, no server). Everything on the
images comes from the extension and the design system copies it ships.

Usage: python tools/store-images.py   (CHROME=<path> picks the browser)
Standard library only. The store icon comes from scripts/app-icon-sharewerk.py.
"""

from __future__ import annotations

import functools
import http.server
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "chrome-web-store"

# Example data only: the account IDs are made up.
STUB = r"""
// Store images only: a stand-in for the chrome APIs with example data, and the page language.
(function () {
  const params = new URLSearchParams(location.search);
  const lang = params.get("lang") || "en";
  Object.defineProperty(navigator, "language", { get: () => lang });
  const scene = params.get("scene") || "confirm";
  const server = "https://sharewerk.example.com";
  const store = {
    server,
    "platform:instagram": scene === "confirm"
      ? { status: "confirm", pending: "51234567890", error: "" }
      : { status: "sent", account: "51234567890", sent: "x", sentTo: server, sentAt: Date.now() - 2 * 3600e3, error: "" },
    "platform:facebook": { status: "sent", account: "100012345678901", sent: "x", sentTo: server, sentAt: Date.now() - 26 * 3600e3, error: "" },
  };
  const jar = {
    "instagram.com": [
      { domain: ".instagram.com", name: "sessionid", value: "51234567890%3Aexample" },
      { domain: ".instagram.com", name: "ds_user_id", value: "51234567890" },
    ],
    "facebook.com": [
      { domain: ".facebook.com", name: "c_user", value: "100012345678901" },
      { domain: ".facebook.com", name: "xs", value: "example" },
    ],
  };
  const states = {
    instagram: { state: scene === "confirm" ? "unknown" : "ok", source: "extension", updated: 1 },
    facebook: { state: "ok", source: "extension", updated: 1 },
  };
  window.chrome = {
    cookies: { getAll: async ({ domain }) => jar[domain] || [] },
    storage: {
      local: {
        get: async (keys) => {
          const list = Array.isArray(keys) ? keys : [keys];
          return Object.fromEntries(list.filter((k) => k in store).map((k) => [k, structuredClone(store[k])]));
        },
        set: async (items) => { Object.assign(store, structuredClone(items)); },
      },
    },
    permissions: { contains: async () => true, request: async () => true, remove: async () => true },
    action: { setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {}, setBadgeTextColor: async () => {} },
    runtime: { openOptionsPage: () => {}, getManifest: () => ({ version: "0.1.2" }) },
    tabs: { create: () => {} },
  };
  window.fetch = async (url) => {
    const body = String(url).endsWith("/api/cookies") ? { platforms: states } : { state: "unknown", source: "extension", updated: 2 };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  };
})();
"""

# The popup as Chrome shows it below its toolbar icon, on the page background of the design system.
STAGE = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<script src="theme.js"></script>
<link rel="stylesheet" href="azentrius/tokens.css"><link rel="stylesheet" href="azentrius/bundle.css">
<style>
  html, body {{ margin: 0; block-size: 100%; }}
  body {{ display: grid; place-items: center; background: var(--bg-page); }}
  iframe {{ inline-size: 380px; block-size: 640px; border: 1px solid var(--line); border-radius: var(--radius-medium); background: var(--bg-page); }}
</style></head>
<body><iframe src="popup.html?lang={lang}&scene={scene}" title="Sharewerk"></iframe></body></html>
"""

# Sign and word mark on brand ink, as on the cover of the design system.
PROMO = """<!doctype html>
<html lang="en" data-theme="azentrius-dunkel"><head><meta charset="utf-8">
<link rel="stylesheet" href="azentrius/tokens.css"><link rel="stylesheet" href="azentrius/bundle.css">
<style>
  /* A fixed box: Chrome's window can be wider than the 440 pixels of the screenshot. */
  html, body {{ margin: 0; background: #0A0A0F; }}
  body {{ inline-size: 440px; block-size: 280px; display: flex; align-items: center; justify-content: center; gap: 16px; }}
  img {{ inline-size: 88px; block-size: 88px; border-radius: 19px; }}
  .az-page-title {{ font-size: 38px; }}
</style></head>
<body><img src="sign.svg" alt=""><h1 class="az-page-title az-page-title--dot">Sharewerk</h1></body></html>
"""

SHOTS = [
    # file name, page (both per language)
    ("screenshot-1-{lang}.png", "stage-{lang}-confirm.html"),  # an account waits for confirmation
    ("screenshot-2-{lang}.png", "stage-{lang}-sent.html"),  # both platforms sent and valid
    ("screenshot-3-{lang}.png", "options.html?lang={lang}&scene=sent"),  # the settings page
]


def browser() -> str:
    candidates = [os.environ.get("CHROME", ""),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    candidates += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise SystemExit("no Chrome or Edge found; set CHROME=<path>")


def build_extension(out: Path) -> Path:
    spec = importlib.util.spec_from_file_location("build_extension", ROOT / "tools" / "build-extension.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    folder, _ = module.build(out)
    return folder


def prepare(site: Path) -> None:
    (site / "stub.js").write_text(STUB, encoding="utf-8")
    for page in ("popup.html", "options.html"):
        path = site / page
        html = path.read_text(encoding="utf-8")
        path.write_text(html.replace('<script src="theme.js"></script>', '<script src="stub.js"></script>\n  <script src="theme.js"></script>', 1), encoding="utf-8")
    for lang in ("en", "de"):
        for scene in ("confirm", "sent"):
            (site / f"stage-{lang}-{scene}.html").write_text(STAGE.format(lang=lang, scene=scene), encoding="utf-8")
    (site / "promo.html").write_text(PROMO.format(), encoding="utf-8")
    shutil.copyfile(ROOT / "app" / "static" / "icons" / "sharewerk.svg", site / "sign.svg")


class Quiet(http.server.SimpleHTTPRequestHandler):
    # Module scripts need a JavaScript type; some systems map .js to text/plain.
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript"}

    def log_message(self, *args) -> None:
        pass


def serve(site: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(Quiet, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def shoot(chrome: str, url: str, file: Path, width: int, height: int, profile: Path) -> None:
    subprocess.run([
        chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        f"--user-data-dir={profile}", "--force-device-scale-factor=1", f"--window-size={width},{height}",
        "--virtual-time-budget=4000", f"--screenshot={file}", url,
    ], check=True, capture_output=True, timeout=120)
    print(file.relative_to(ROOT))


def main() -> None:
    chrome = browser()
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        site = build_extension(Path(tmp) / "dist")
        prepare(site)
        server, base = serve(site)
        try:
            for lang in ("en", "de"):
                for name, page in SHOTS:
                    shoot(chrome, base + page.format(lang=lang), OUT / name.format(lang=lang), 1280, 800, Path(tmp) / "profile")
            shoot(chrome, base + "promo.html", OUT / "promo-small.png", 440, 280, Path(tmp) / "profile")
        finally:
            server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
