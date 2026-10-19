# Changelog

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
