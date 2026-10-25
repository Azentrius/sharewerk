# Changelog

## Unreleased

On `main` since 0.1.1: cookies from a browser extension, the cookie state in the health check, packs
from partial downloads, a pause between Instagram downloads, results that can be deleted right away,
and an installed app that keeps working across updates.

**Upgrading:** pull the new image. Instagram downloads now start at least 20 seconds apart
(`SHAREWERK_INSTAGRAM_PAUSE`, `0` switches the pause off). The browser extension is optional; the
cookie file keeps working.

- **Browser extension for the cookies.** A Chrome extension (`extension/`, built by
  `tools/build-extension.py`, attached to each release) sends the cookies of Instagram and Facebook
  whenever you log in there, and only for the account you confirmed once in its menu. Sharewerk keeps
  them in `/data/cookies/<platform>.txt` (mode 600); they take precedence over the cookie file and can
  be deleted from the extension's settings page. New API, behind the login: `GET /api/cookies`, and
  `PUT` and `DELETE /api/cookies/<platform>`, which also need the header `X-Sharewerk-Client`.
- **Cookies per platform.** Each download gets only the cookies of its own platform; before, a
  Facebook download got the Instagram cookies too.
- **Cookie state in the health check.** `/healthz` adds `"cookies"` (what the last Instagram download
  found: `ok`, `expired`, `missing` or `unknown`) and `"cookie_states"` with the same for every
  platform. It never turns the check red; a keyword monitor on `"cookies":"expired"` warns when the
  cookies run out. After a restart the state comes from the jobs still kept.
- **Packs from partial downloads.** When gallery-dl and yt-dlp both stop with an error after some
  files, the bigger part becomes a pack marked “This pack is incomplete”, with a line in `post.txt`
  and a button to prepare the post again. In 0.1.1 such a download counted as failed.
- **Pause between Instagram downloads.** New setting `SHAREWERK_INSTAGRAM_PAUSE`, 20 seconds by
  default between the starts of two Instagram downloads, so several shares in a row do not look like
  a burst of requests from the account; the page says so while a post waits. Facebook posts never
  wait.
- **Delete a result right away.** A trash icon in “Recently prepared” (`DELETE /api/jobs/<id>`)
  deletes a finished or failed result with its files instead of after `SHAREWERK_RETENTION_HOURS`. A
  delete that stops halfway leaves a failed job that is never handed out again and can be deleted
  again.
- **Transcription progress.** The page shows how far the transcription is, in percent.
- **Facebook login errors** get their own message, “Facebook asks for a login for this post”; the
  Instagram one now reads “Instagram asks for a login”.
- **Fix: the installed app did not start after an update.** The service worker of 0.1.1 served its
  cached scripts to a newer page. Pages now load scripts and stylesheets with a content hash in the
  URL, so page and scripts always fit together.
- **Fix: a partial pack after a login error reported the cookies as fine.** The cookie state now
  comes from the download, not from the pack.
- **Hardening:** a host that only ends with `instagram.com` or `facebook.com`, such as
  `evilinstagram.com`, no longer counts as Instagram or Facebook. The host allowlist already refused
  such links.
- **Docs:** the README and `SECURITY.md` describe the login cookie, the public health check and where
  cookies are kept; `.env.example` lists every setting; NOTICE adds PyAV and its FFmpeg libraries; the
  README has a trademark notice.

## 0.1.1 – 2026-10-20

Fixes from a code review: shares no longer mix up posts, incomplete downloads count as failed, and a
full or read-only data volume no longer stops the processing unnoticed.

**Upgrading:** pull the new image. `/healthz` now answers 503 when posts cannot be processed, so an
uptime monitor on it reports such an outage.

- **Fix: a share could contain files of the previous post.** The browser cached the files of a pack
  by name only. A download of a post you had already left could fill the cache again after
  “Prepare another post”, and the next share sent the old post's text. Files are now cached per post,
  and late answers for a post you left change nothing on the page.
- **Fix: incomplete downloads passed as complete.** When gallery-dl or yt-dlp ended with an error
  after some files, the pack held just these files, without a warning. Such a download now counts as
  failed, and the other tool is tried. The configured limits (number of items, file size) still give
  a pack.
- **Fix: a full data volume stopped the processing.** A failed write of a post's state ended the only
  worker, every later post waited forever, and `/healthz` still said ok. The worker now keeps running:
  such a post ends with “The server could not save the post” and a button that sends the original
  share again. A failed attempt no longer blocks later ones for the same link. `/healthz` answers 503
  with `worker_stopped` or `storage_failed`, also right after a restart, and recovers by itself once
  writing works again.
- **Fix: relative paths.** With `SHAREWERK_DATA_DIR=./data` from the development start in the README,
  downloads landed in a nested folder and were not found. Configured paths are now resolved before
  the downloaders start; cookies and the gallery-dl config included.
- **Tests:** gallery-dl and yt-dlp are stood in for by a real subprocess, write errors are simulated,
  and `app.js` has tests that run with `node --test` in CI.

## 0.1.0 – 2026-10-20

First release: share an Instagram or Facebook post from Android and get it back as one share-ready pack.

- **Share target:** installed from Chrome, Sharewerk appears in Android's share menu and takes the shared
  link; the share target uses `GET`, so it also works behind an authenticating proxy.
- **Downloads:** gallery-dl and yt-dlp fetch carousels, reels, videos and stories, with the cookies of a
  secondary account; only links to Instagram and Facebook hosts are accepted.
- **Pack:** every image as JPEG (long edge 1568 px), key frames of videos at scene changes, a
  timestamped transcript (faster-whisper) and `post.txt` with source, author, date, caption and an index
  of all pictures. When the pictures do not fit into one share (Android takes 10 files), they are
  combined into numbered contact sheets, so the whole post still goes out in one share.
- **Access:** own access token, or `SHAREWERK_AUTH_MODE=none` behind a proxy such as Pomerium.
- **Interface** in English and German, light and dark, following the Azentrius Design System.
- **Container:** non-root, read-only root filesystem, no capabilities; results are deleted after 24 hours.
- **Image:** `ghcr.io/azentrius/sharewerk:latest` is rebuilt on every change and every Monday with the
  newest downloaders; each release gets its own tag `X.Y.Z`. The label `org.opencontainers.image.version`
  carries the release version, also on `latest`, so image update monitors can tell a new version from a
  newer build.
