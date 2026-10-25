<p align="center"><img src="app/static/icons/icon-192.png" width="96" alt=""></p>

# Sharewerk

**Share an Instagram or Facebook post from your Android phone and get it back as a clean, share-ready pack:** every carousel image in full quality, key frames and a transcript for videos, and the caption as text. Then pass it straight on to an AI chat app, a messenger or anywhere else in the share menu.

No more screenshots of every slide, no more screen recordings.

> **Status:** personal project, published in case it is useful to others. It works for me, but comes with no support promise and may break whenever Instagram or Facebook change something. Use at your own risk.

## How it works

```
Instagram / Facebook app
   │  Share → Sharewerk                      (Android share sheet)
   ▼
Sharewerk PWA on your phone  ──link──▶  Sharewerk server (Docker)
                                          ├─ gallery-dl / yt-dlp   download the post
                                          ├─ Pillow                images → JPEG, 1568 px
                                          ├─ ffmpeg                video → key frames, audio
                                          └─ faster-whisper        audio → transcript
   ◀──── images + post.txt ───────────────┘
   │  Share → Claude, ChatGPT, WhatsApp, …   (Android share sheet)
```

Sharewerk is a Progressive Web App (a website you install like an app). Once installed through Chrome, it registers as a share target, so it appears in Android's share menu. The phone only sends the link; all downloading and processing happens on your server.

What you get for a post:

| Post contains | Pack contains |
|---|---|
| Image carousel | Every image as JPEG (long edge 1568 px, sharp enough to read text, small enough to share fast) |
| Video / reel | Key frames at scene changes plus a timestamped transcript |
| Anything | A `post.txt` with source, author, date, caption and an index of all pictures |

Android allows at most 10 files per share. If a post has more pictures than fit, Sharewerk combines them into numbered contact sheets so the whole post still goes out in **one** share (and lands in one chat). Single pictures and the original media files can be shared separately.

**iPhone is not supported:** Safari does not implement the Web Share Target API, so a web app cannot appear in the iOS share sheet.

## Requirements

- A server with Docker and Docker Compose (2 CPU cores and 3 GB RAM are plenty)
- A domain with HTTPS in front of it (PWAs only install from secure origins)
- An Android phone with Chrome
- For Instagram: a **secondary** Instagram account (see [Cookies](#cookies))

## Quick start

```bash
git clone https://github.com/Azentrius/sharewerk.git
cd sharewerk
cp .env.example .env
sed -i "s/^SHAREWERK_AUTH_TOKEN=.*/SHAREWERK_AUTH_TOKEN=$(openssl rand -hex 32)/" .env
mkdir -p secrets
docker compose up -d
docker compose logs -f sharewerk
```

The service now listens on `127.0.0.1:8080`. Put a TLS reverse proxy in front of it, for example [Caddy](https://caddyserver.com):

```caddyfile
sharewerk.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Open `https://sharewerk.example.com` on your phone, enter the token from `.env` once, then install the app (see [Install on Android](#install-on-android)).

The first video you process downloads the Whisper speech model (about 500 MB for `small`) into the data volume. That run takes a bit longer.

## Cookies

Instagram shows almost nothing to logged-out visitors, so the downloaders need the cookies of a logged-in account. Facebook videos often work without cookies; Facebook posts that only logged-in accounts can see need them too.

**Use a secondary account, not your main one.** Automated access violates Meta's terms of use, and accounts used this way can be rate-limited or blocked. To make that less likely, Sharewerk waits `SHAREWERK_INSTAGRAM_PAUSE` seconds (20 by default) between the starts of two Instagram downloads; the page says so while a post waits.

There are two ways to give Sharewerk the cookies: the [browser extension](#browser-extension-chrome) sends them whenever you log in, or you put a [cookie file](#cookie-file-by-hand) on the server by hand. Sharewerk reads them again for every job, so there is no need to restart it. Each download gets only the cookies of its own platform, and cookies sent by the extension take precedence over the file.

**Cookies are a logged-in session. Treat them like a password.** `secrets/` is git-ignored, and the gitleaks configuration in this repository detects Instagram/Facebook session cookies if one ever ends up in a commit.

### Browser extension (Chrome)

The extension in `extension/` sends the cookies of Instagram and Facebook to your Sharewerk server when you log in there, and again whenever the login changes. It uses your login at Sharewerk in the same browser (the token login, or your proxy's such as Pomerium), so it needs no secret of its own.

1. Create a separate Chrome profile for the secondary accounts and do nothing else in it.
2. Download `sharewerk-extension-X.Y.Z.zip` from the [latest release](https://github.com/Azentrius/sharewerk/releases/latest) and unpack it, or build it yourself with `python tools/build-extension.py` (the result is in `dist/`).
3. In that profile open `chrome://extensions`, switch on **Developer mode**, click **Load unpacked** and pick the unpacked folder.
4. The settings page opens: enter your Sharewerk address and allow the access Chrome asks for.
5. Sign in to Sharewerk in this profile, then log in to Instagram, and to Facebook if you want it.
6. Open the extension's menu (its icon in the toolbar) and confirm the account with **Use account**. From then on the extension sends that account's cookies by itself. Another account in the same browser, such as your main one, is never sent without asking again.

The icon shows `?` while an account waits for your confirmation and `!` when the cookies cannot reach Sharewerk (no address, no login at Sharewerk, server unreachable or an error); the menu says which and what to do. When the login at your proxy expires (Pomerium: `cookie_expire`), the extension waits until you sign in to Sharewerk again in that profile, then sends what waited.

What the extension can do: read the cookies of instagram.com and facebook.com, and send them to the one address you entered. It runs no code on web pages and loads no code from the internet. Sharewerk keeps the cookies in the data volume (`/data/cookies/<platform>.txt`, readable by the container user only) and never writes their values to a log. In the settings page you can delete them from Sharewerk again; the extension then asks before it sends an account again.

### Cookie file by hand

1. Create a separate browser profile, log in to the secondary account there, and do nothing else in that profile. This keeps the cookie file limited to that one account.
2. Export the cookies in Netscape `cookies.txt` format, for example with the browser extension "Get cookies.txt LOCALLY" (Chrome) or "cookies.txt" (Firefox). In Chrome, take the one with "LOCALLY" in its name: an older extension called "Get cookies.txt" was removed from the Chrome Web Store as malware. Export instagram.com, and facebook.com if you want it.
3. Close the browser profile without logging out (logging out invalidates the cookies).
4. Copy the file to the server, put it in place so that only the container user (uid 10001) can read it, and delete the copy:

```bash
sudo install -o 10001 -g 10001 -m 600 cookies.txt secrets/cookies.txt
shred -u cookies.txt
```

Delete the exported file on your computer as well. Cookies expire after a while, or sooner when Instagram gets suspicious. When Sharewerk reports "login required", export them again.

## Install on Android

1. Open your Sharewerk URL in **Chrome** and sign in.
2. Chrome menu ⋮ → **Install app** (on some versions: "Add to home screen").
3. In Instagram tap **Share** → **Share to…** / **More**, pick **Sharewerk**.
4. When the pack is ready, tap **Share** and pick the target app.

If Sharewerk does not appear in the share menu, it was added as a plain bookmark rather than installed. Remove it and install again from Chrome's menu.

## Running behind an authenticating proxy

If you already have an identity-aware proxy (Pomerium, oauth2-proxy, Authelia, Cloudflare Access …), let it handle logins and switch Sharewerk's own token off:

```env
SHAREWERK_AUTH_MODE=none
```

Only do this if the port is unreachable except through the proxy. Two things are already taken care of for proxies:

- The share target uses `GET`, so the shared link survives a redirect to the proxy's login page and back.
- The manifest is loaded with credentials (`crossorigin="use-credentials"`), so Chrome can install the app through the proxy. If your proxy still blocks it, make `/manifest.webmanifest`, `/sw.js` and `/static/*` public; they contain nothing private.

Example Pomerium routes, with a public health check for monitoring:

```yaml
routes:
  - from: https://sharewerk.example.com
    path: /health
    prefix_rewrite: /healthz
    to: http://10.0.0.5:8080
    allow_public_unauthenticated_access: true
  - from: https://sharewerk.example.com
    to: http://10.0.0.5:8080
    timeout: 600s
    policy:
      - allow:
          or:
            - email:
                is: you@example.com
```

Sharewerk answers `GET /healthz` with `{"ok":true,"cookies":"ok","cookie_states":{"instagram":"ok","facebook":"missing"}}`. Pomerium, however, answers `/healthz` and `/ping` itself, so a monitor on those paths only shows that Pomerium is up. The first route passes `/health` to Sharewerk's `/healthz` without a login; point your monitor there and check for `"ok":true`. Everything else stays behind the policy. Keep the public route first, because Pomerium uses the first route that matches. The longer `timeout` gives large files time to download over a slow connection; Pomerium's default is 30 seconds.

The health check has two parts:

- `"ok"` is `false` (with HTTP 503) when posts cannot be processed at all: `worker_stopped` or `storage_failed` in `"problem"`.
- `"cookies"` says what the last Instagram download found: `ok`, `expired` (Instagram asked for a login), `missing` (no Instagram cookies, neither sent by the extension nor in the cookie file) or `unknown` (no Instagram download started since the cookies were last written, e.g. right after you logged in again or exported new cookies). It never turns the check red, because Facebook works without cookies.
- `"cookie_states"` has the same for every platform. For Facebook, `expired` can also mean that the last post was visible to its author's friends only.

For a warning when the cookies run out, add a second keyword monitor on the same URL that alerts when it finds `"cookies":"expired"` (in Uptime Kuma: keyword monitor with "Invert Keyword"). After a restart the state comes from the jobs still kept (`SHAREWERK_RETENTION_HOURS`).

## Updating

Instagram and Facebook change constantly; when downloads start failing, a newer gallery-dl or yt-dlp almost always fixes it. The image `ghcr.io/azentrius/sharewerk:latest` is rebuilt every week with the newest versions, so updating is:

```bash
docker compose pull && docker compose up -d
```

If you build locally: `docker compose build --pull --no-cache && docker compose up -d`.

Images carry a signed build provenance; check one with `gh attestation verify oci://ghcr.io/azentrius/sharewerk:latest --repo Azentrius/sharewerk`.

### Image tags and labels

| Tag | What it is |
|---|---|
| `latest` | The newest build of `main`, rebuilt on every change and every Monday with the newest downloaders. Use this one. |
| `X.Y.Z` (e.g. `0.1.0`) | A release. It keeps the downloaders of its build day and never changes. |
| `YYYYMMDD` | The Monday rebuild of that day. |
| `sha-<commit>` | The build of one commit on `main`. |

Every image carries the OCI labels `org.opencontainers.image.version` (the version in `app/__init__.py`, which is the last release, also on `latest`), `org.opencontainers.image.revision` (the commit) and `org.opencontainers.image.source`. Image update monitors can match the version label to the release tag, and show a newer build under `latest` as an update.

## Configuration

All settings are environment variables in `.env`. `.env.example` documents each one. The most important:

| Variable | Default | Meaning |
|---|---|---|
| `SHAREWERK_AUTH_MODE` | `token` | `token` = own login, `none` = behind an auth proxy |
| `SHAREWERK_AUTH_TOKEN` | – | Access token, at least 24 characters |
| `SHAREWERK_WHISPER_MODEL` | `small` | `tiny` … `large-v3`, or `off` |
| `SHAREWERK_WHISPER_LANGUAGE` | auto | Force a language, e.g. `de` |
| `SHAREWERK_IMAGE_MAX_EDGE` | `1568` | Long edge of shared images in px |
| `SHAREWERK_MAX_FRAMES` | `8` | Key frames per video |
| `SHAREWERK_RETENTION_HOURS` | `24` | Results are deleted afterwards |
| `SHAREWERK_INSTAGRAM_PAUSE` | `20` | Seconds between the starts of two Instagram downloads (`0` = no pause) |

## Security notes

- The downloaders only ever receive URLs on an allowlist of Instagram and Facebook hosts (`SHAREWERK_ALLOWED_HOSTS`). This prevents the server from being used to fetch arbitrary or internal addresses.
- Never run Sharewerk as an open service for other people. The cookies are yours, and so is the responsibility for what is downloaded with them.
- Only the browser extension sends cookies (`PUT /api/cookies/<platform>`), with your login at Sharewerk and a header that a web page cannot add to a request to another site, so no other site can plant cookies through your browser. Sharewerk takes only cookies of the platform's own domain and refuses anything that could break the cookie file. Keep `/api/cookies` behind your proxy's policy, like everything except `/health`.
- The container runs as a non-root user with a read-only root filesystem and no Linux capabilities.
- Results are deleted after `SHAREWERK_RETENTION_HOURS`, or right away with the trash icon in "Recently prepared" (`DELETE /api/jobs/<id>`; a post that is still being prepared cannot be deleted).

## Legal

Sharewerk is a tool for personal use: it saves you from taking screenshots of posts you can already see. Automated access to Instagram and Facebook is against Meta's terms of use, and the content of a post belongs to its author. You are responsible for how you use it. This project is not affiliated with or endorsed by Meta Platforms. Instagram, Facebook and the other app names in this README are trademarks of their respective owners.

## Troubleshooting

| Message | Usual cause | Fix |
|---|---|---|
| Login required, or `"cookies":"expired"` in `/healthz` | Cookies missing or expired | Log in to Instagram again in the extension's browser profile, or export new cookies; the state turns `unknown` as soon as new cookies arrive, `ok` after the next Instagram download |
| Download failed | Downloader outdated | Pull or rebuild the image |
| Facebook asks for a login for this post | The post is visible to logged-in accounts only; Sharewerk has no (valid) Facebook cookies | Log in to a secondary Facebook account in the extension's browser profile, or export its cookies as well |
| The extension's icon shows `!`, "Sharewerk asks for a login" | No login at Sharewerk in that browser profile, or it expired | Open Sharewerk in that profile and sign in; the extension then sends by itself |
| The extension's icon shows `?` | An account waits for your confirmation | Open the extension's menu; confirm with "Use account" only if it is the secondary account |
| Too many requests | Rate limit on the account | Wait, then try again |
| This pack is incomplete | The download stopped after some items, often at a rate limit; you get what arrived, and `post.txt` says so | Prepare the post again later for the rest |
| Not in share menu | App not installed | Install from Chrome's menu |
| Transcript says "music only" | No speech in the audio | Expected for music reels |
| The server could not save the post | Data volume full or read-only | Free up space, then prepare the post again |
| `/healthz` answers 503 | `worker_stopped`: the job worker ended; `storage_failed`: job states cannot be saved | Check the logs and the data volume, restart Sharewerk |

Logs: `docker compose logs -f sharewerk`

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ruff check
python -m pytest
node --test tests/js/app.test.mjs tests/js/extension.test.mjs   # no npm packages needed
SHAREWERK_AUTH_MODE=none SHAREWERK_DATA_DIR=./data SHAREWERK_COOKIE_SECURE=false python -m app.main
python tools/build-extension.py   # the browser extension, in dist/
```

Install the secret-scanning pre-commit hook once: `pipx install pre-commit && pre-commit install`.

Changes are listed in [CHANGELOG.md](CHANGELOG.md); the version lives in `app/__init__.py`. Releases are made by the `release` workflow from `main`.

Code layout: `app/urls.py` (link validation), `app/fetch.py` (downloaders), `app/cookies.py` (cookies per platform), `app/process.py` (images, frames, contact sheets, text), `app/transcribe.py` (Whisper), `app/jobs.py` (queue), `app/main.py` (HTTP), `app/static/` (PWA), `app/static/azentrius/` (design system, copied unchanged), `extension/` (browser extension; `tools/build-extension.py` adds the design system, `theme.js`, `icons.js` and the license texts from the app).

## Design

The interface follows the Azentrius Design System, theme "Azentrius hell" or "Azentrius dunkel" depending on the device setting. `app/static/azentrius/` holds the system's `tokens.css`, `bundle.css` and font files, copied unchanged; never edit them by hand, replace them with a newer copy of the design system instead. `app/static/app.css` contains only layout the design system leaves to the app, and `extension/extension.css` the same for the extension, which the build gives the same copies.

## License

Sharewerk is licensed under the [Apache License 2.0](LICENSE); see also [NOTICE](NOTICE). Not covered by it: the Azentrius brand, i.e. the wordmark "Azentrius.", its signs and the product names, including "Sharewerk" and the Sharewerk sign (all rights reserved).

Bundled with their own licenses (texts in [LICENSES/](LICENSES/)): the design system's CSS (Apache-2.0), the fonts DM Sans, DM Serif Display and Red Hat Mono (SIL OFL 1.1), and the icons (Font Awesome Free 5 under CC BY 4.0, one PatternFly icon under MIT). The Docker image additionally contains GPL-licensed gallery-dl and FFmpeg; see [NOTICE](NOTICE).

Made by [Azentrius](https://azentrius.com).
