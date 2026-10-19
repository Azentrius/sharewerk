# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Report them privately through GitHub instead:
[Report a vulnerability](https://github.com/Azentrius/sharewerk/security/advisories/new)
(tab **Security → Report a vulnerability** in this repository).

Please include:

- what is affected (link handling, downloads, processing, sign-in, the app in
  the browser, the Docker image; version or commit),
- steps to reproduce,
- the impact you expect.

We aim to acknowledge reports within 7 days. This is a small project, so a fix
may take longer; we will keep you informed and credit you in the advisory
unless you prefer to stay anonymous.

## Supported versions

Only the latest release, the image tag `latest` and the latest state of the
`main` branch receive security fixes.

## What Sharewerk does

Sharewerk downloads posts with the cookies of a logged-in account and runs
gallery-dl, yt-dlp and FFmpeg on what it gets. That is why:

- the downloaders only ever receive links to hosts on an allowlist of
  Instagram and Facebook addresses; short links are followed by hand, and
  every hop is checked against the allowlist again;
- the downloaders and FFmpeg run as separate programs with argument lists,
  never through a shell;
- the cookie file is mounted read-only, copied per job, deleted after the
  job and never logged;
- with `SHAREWERK_AUTH_MODE=token` every page and API call needs the access
  token (as a session cookie or bearer token), compared in constant time;
  `SHAREWERK_AUTH_MODE=none` is meant only behind an authenticating proxy
  whose port is the only way in;
- files of a job are served only by their names in the job's manifest, from
  inside the job's folder;
- pages are served with a strict Content Security Policy (no inline scripts
  or styles, no framing);
- the container runs as a non-root user with a read-only root filesystem and
  no Linux capabilities;
- results are deleted after `SHAREWERK_RETENTION_HOURS`.

## Especially relevant

Reports are particularly welcome for:

- links that make the server fetch an address outside the allowlist
  (server-side request forgery), also through redirects or the downloaders,
- shared text or post metadata that gets interpreted as a command, an
  option of a downloader or a path outside the job's folder,
- the cookie file or the access token appearing in a log, a URL, a page, a
  job's files or any other file,
- ways around the access token or the sign-in, or open redirects,
- one job reading or serving files of another job or of the server,
- post content (captions, titles, transcripts) that the app renders as HTML
  or script,
- images on GHCR or release archives that do not match the tagged source or
  whose build provenance does not verify.
