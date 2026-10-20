# Changelog

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
