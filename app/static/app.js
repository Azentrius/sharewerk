// SPDX-License-Identifier: Apache-2.0
"use strict";

// ---------------------------------------------------------------------- i18n
// Source strings in English, German as first translation (Azentrius Design System, Sprache).
const I18N = {
  en: {
    "home.installTitle": "Sharewerk only appears in the share menu once it is installed",
    "home.installBody": "Chrome menu ⋮ → “Install app”. Then tap Share in Instagram or Facebook and pick Sharewerk.",
    "home.title": "Prepare a post",
    "home.desc": "Sharewerk fetches the images, video stills and text of a post so you can pass everything on in one share.",
    "home.label": "Link to the post",
    "home.help": "A post, reel or story from Instagram or Facebook.",
    "home.submit": "Prepare post",
    "recent.title": "Recently prepared",
    "recent.post": "Post",
    "recent.status": "Status",
    "recent.time": "Time",
    "recent.actions": "Actions",
    "recent.open": "Open result",
    "recent.emptyTitle": "No posts prepared yet",
    "recent.emptyBody": "Share a post from Instagram or Facebook to Sharewerk, or paste its link above. Results stay here for {h} hours.",
    "status.queued": "Waiting",
    "status.running": "In progress",
    "status.done": "Ready",
    "status.error": "Failed",
    "work.title": "Preparing the post",
    "step.queued": "Waiting for a free slot …",
    "step.downloading": "Downloading the post …",
    "step.processing": "Preparing images and video stills …",
    "step.transcribing": "Transcribing the audio …",
    "queue": "Position {n} in the queue",
    "done.titleAuthor": "Post by @{a}",
    "done.titleName": "Post by {a}",
    "done.titlePlain": "{p} post",
    "done.images": "{n} images",
    "done.image": "1 image",
    "done.videos": "{n} videos",
    "done.video": "1 video",
    "done.packPictures": "The pack contains {n} pictures and the text.",
    "done.packPicture": "The pack contains 1 picture and the text.",
    "done.packSheets": "The pack contains {n} pictures on {s} sheets and the text.",
    "done.packText": "The pack contains the text.",
    "done.share": "Share pack",
    "done.copy": "Copy text",
    "done.open": "Open post",
    "done.textTitle": "Text that is shared",
    "done.new": "Prepare another post",
    "done.loading": "Loading …",
    "done.downloadIntro": "This browser cannot share files. Download them instead:",
    "thumbs.label": "Pictures in the pack",
    "thumbs.image": "Image",
    "thumbs.frame": "Video, {t}",
    "thumbs.altImage": "Picture {n}: image {i} of the post",
    "thumbs.altFrame": "Picture {n}: still from the video at {t}",
    "more.title": "Share separately",
    "more.desc": "Android shares at most 10 files at once. Here you pass on the single pictures or the original files.",
    "more.single": "Share single pictures",
    "more.singlePart": "Share single pictures, part {i} of {n}",
    "more.original": "Share original files",
    "more.originalPart": "Share original files, part {i} of {n}",
    "alert.copiedTitle": "Text copied",
    "alert.copiedBody": "You can now paste it into any app.",
    "alert.copyFailedTitle": "The text could not be copied",
    "alert.copyFailedBody": "The browser denied access to the clipboard. Select the text below and copy it by hand.",
    "alert.tapAgainTitle": "The files are loaded",
    "alert.tapAgainBody": "Tap the button again to share them.",
    "alert.cannotShareTitle": "This device cannot share these files",
    "alert.cannotShareBody": "Download them with the links in the first card.",
    "alert.loadFailedTitle": "The files could not be loaded",
    "alert.loadFailedBody": "Check the connection and tap the button again.",
    "error.post": "Post:",
    "error.retry": "Prepare post again",
    "field.no_url": "Paste a link that starts with https://.",
    "field.host_not_allowed": "Paste a link to Instagram or Facebook.",
    "field.unsupported_link": "Paste the link to a single post, reel or story, not to a profile.",
    "err.auth_required.title": "Instagram or Facebook asks for a login",
    "err.auth_required.body": "The cookies of a logged-in account are missing on the server or have expired. Export them again to secrets/cookies.txt (README, section “Cookies”).",
    "err.rate_limited.title": "Too many requests to Instagram or Facebook",
    "err.rate_limited.body": "The account is being throttled right now. Try again in a few minutes.",
    "err.not_found.title": "Post not found",
    "err.not_found.body": "It was deleted, is private, or the link is incomplete. Check the link in the app.",
    "err.unsupported.title": "This kind of post is not supported",
    "err.unsupported.body": "Sharewerk handles posts with images and videos, reels and stories.",
    "err.timeout.title": "The download took too long",
    "err.timeout.body": "Try again. If it keeps happening, the server's connection to Instagram or Facebook is disturbed.",
    "err.unreachable.title": "The server cannot reach Instagram or Facebook",
    "err.unreachable.body": "Check the server's network, DNS and proxy.",
    "err.download_failed.title": "The post could not be downloaded",
    "err.download_failed.body": "Usually gallery-dl or yt-dlp needs an update. Pull the current image with docker compose pull and restart Sharewerk.",
    "err.interrupted.title": "Preparing the post was interrupted",
    "err.interrupted.body": "The server restarted in the meantime. Prepare the post again.",
    "err.internal.title": "An error occurred while preparing the post",
    "err.internal.body": "The details below help with debugging. docker compose logs sharewerk shows the logs.",
    "err.storage_failed.title": "The server could not save the post",
    "err.storage_failed.body": "Its data volume is probably full or read-only. Free up space on the server, then prepare the post again.",
    "err.job_not_found.title": "This result has expired",
    "err.job_not_found.body": "Results are deleted after {h} hours. Prepare the post again.",
    "err.network.title": "No connection to the server",
    "err.network.body": "Check the phone's internet connection and try again.",
    "footer.source": "Source code",
  },
  de: {
    "home.installTitle": "Im Teilen-Menü erscheint Sharewerk erst nach der Installation",
    "home.installBody": "Chrome-Menü ⋮ → „App installieren“. Danach in Instagram oder Facebook auf Teilen tippen und Sharewerk wählen.",
    "home.title": "Beitrag aufbereiten",
    "home.desc": "Sharewerk holt Bilder, Standbilder und Text eines Beitrags, damit du alles mit einer Freigabe weitergeben kannst.",
    "home.label": "Link zum Beitrag",
    "home.help": "Ein Beitrag, Reel oder eine Story von Instagram oder Facebook.",
    "home.submit": "Beitrag aufbereiten",
    "recent.title": "Zuletzt aufbereitet",
    "recent.post": "Beitrag",
    "recent.status": "Status",
    "recent.time": "Zeit",
    "recent.actions": "Aktionen",
    "recent.open": "Ergebnis öffnen",
    "recent.emptyTitle": "Noch keine Beiträge aufbereitet",
    "recent.emptyBody": "Teile einen Beitrag aus Instagram oder Facebook an Sharewerk oder füge oben seinen Link ein. Ergebnisse bleiben {h} Stunden hier.",
    "status.queued": "Wartet",
    "status.running": "Wird aufbereitet",
    "status.done": "Fertig",
    "status.error": "Fehlgeschlagen",
    "work.title": "Beitrag wird aufbereitet",
    "step.queued": "Wartet auf einen freien Platz …",
    "step.downloading": "Beitrag wird heruntergeladen …",
    "step.processing": "Bilder und Standbilder werden aufbereitet …",
    "step.transcribing": "Ton wird transkribiert …",
    "queue": "Platz {n} in der Warteschlange",
    "done.titleAuthor": "Beitrag von @{a}",
    "done.titleName": "Beitrag von {a}",
    "done.titlePlain": "Beitrag auf {p}",
    "done.images": "{n} Bilder",
    "done.image": "1 Bild",
    "done.videos": "{n} Videos",
    "done.video": "1 Video",
    "done.packPictures": "Das Paket enthält {n} Bilder und den Text.",
    "done.packPicture": "Das Paket enthält 1 Bild und den Text.",
    "done.packSheets": "Das Paket enthält {n} Bilder auf {s} Bögen und den Text.",
    "done.packText": "Das Paket enthält den Text.",
    "done.share": "Paket teilen",
    "done.copy": "Text kopieren",
    "done.open": "Beitrag öffnen",
    "done.textTitle": "Text, der mitgeteilt wird",
    "done.new": "Weiteren Beitrag aufbereiten",
    "done.loading": "Lädt …",
    "done.downloadIntro": "Dieser Browser kann keine Dateien teilen. Lade sie stattdessen herunter:",
    "thumbs.label": "Bilder im Paket",
    "thumbs.image": "Bild",
    "thumbs.frame": "Video, {t}",
    "thumbs.altImage": "Bild {n}: Bild {i} des Beitrags",
    "thumbs.altFrame": "Bild {n}: Standbild aus dem Video bei {t}",
    "more.title": "Einzeln teilen",
    "more.desc": "Android teilt höchstens 10 Dateien auf einmal. Hier gibst du die Einzelbilder oder die Originaldateien weiter.",
    "more.single": "Einzelbilder teilen",
    "more.singlePart": "Einzelbilder teilen, Teil {i} von {n}",
    "more.original": "Originaldateien teilen",
    "more.originalPart": "Originaldateien teilen, Teil {i} von {n}",
    "alert.copiedTitle": "Text kopiert",
    "alert.copiedBody": "Du kannst ihn jetzt in eine App einfügen.",
    "alert.copyFailedTitle": "Der Text konnte nicht kopiert werden",
    "alert.copyFailedBody": "Der Browser hat den Zugriff auf die Zwischenablage verweigert. Markiere den Text unten und kopiere ihn von Hand.",
    "alert.tapAgainTitle": "Die Dateien sind geladen",
    "alert.tapAgainBody": "Tippe noch einmal auf den Button, um sie zu teilen.",
    "alert.cannotShareTitle": "Dieses Gerät kann diese Dateien nicht teilen",
    "alert.cannotShareBody": "Lade sie über die Links in der ersten Karte herunter.",
    "alert.loadFailedTitle": "Die Dateien konnten nicht geladen werden",
    "alert.loadFailedBody": "Prüfe die Verbindung und tippe noch einmal auf den Button.",
    "error.post": "Beitrag:",
    "error.retry": "Beitrag erneut aufbereiten",
    "field.no_url": "Füge einen Link ein, der mit https:// beginnt.",
    "field.host_not_allowed": "Füge einen Link zu Instagram oder Facebook ein.",
    "field.unsupported_link": "Füge den Link zu einem einzelnen Beitrag, Reel oder einer Story ein, nicht zu einem Profil.",
    "err.auth_required.title": "Instagram oder Facebook verlangt eine Anmeldung",
    "err.auth_required.body": "Auf dem Server fehlen die Cookies eines angemeldeten Kontos, oder sie sind abgelaufen. Exportiere sie neu nach secrets/cookies.txt (README, Abschnitt „Cookies“).",
    "err.rate_limited.title": "Zu viele Anfragen an Instagram oder Facebook",
    "err.rate_limited.body": "Das Konto wird gerade gedrosselt. Versuch es in ein paar Minuten erneut.",
    "err.not_found.title": "Beitrag nicht gefunden",
    "err.not_found.body": "Er wurde gelöscht, ist privat, oder der Link ist unvollständig. Prüfe den Link in der App.",
    "err.unsupported.title": "Diese Art Beitrag wird nicht unterstützt",
    "err.unsupported.body": "Sharewerk verarbeitet Beiträge mit Bildern und Videos, Reels und Storys.",
    "err.timeout.title": "Das Herunterladen hat zu lange gedauert",
    "err.timeout.body": "Versuch es erneut. Bleibt es dabei, ist die Verbindung des Servers zu Instagram oder Facebook gestört.",
    "err.unreachable.title": "Der Server erreicht Instagram oder Facebook nicht",
    "err.unreachable.body": "Prüfe Netzwerk, DNS und Proxy des Servers.",
    "err.download_failed.title": "Der Beitrag konnte nicht heruntergeladen werden",
    "err.download_failed.body": "Meist braucht gallery-dl oder yt-dlp ein Update. Zieh das aktuelle Image mit docker compose pull und starte Sharewerk neu.",
    "err.interrupted.title": "Die Aufbereitung wurde unterbrochen",
    "err.interrupted.body": "Der Server wurde währenddessen neu gestartet. Bereite den Beitrag erneut auf.",
    "err.internal.title": "Bei der Aufbereitung ist ein Fehler aufgetreten",
    "err.internal.body": "Die Details unten helfen bei der Fehlersuche. Die Protokolle zeigt docker compose logs sharewerk.",
    "err.storage_failed.title": "Der Server konnte den Beitrag nicht speichern",
    "err.storage_failed.body": "Vermutlich ist sein Datenspeicher voll oder schreibgeschützt. Gib auf dem Server Platz frei und bereite den Beitrag dann erneut auf.",
    "err.job_not_found.title": "Dieses Ergebnis ist abgelaufen",
    "err.job_not_found.body": "Ergebnisse werden nach {h} Stunden gelöscht. Bereite den Beitrag erneut auf.",
    "err.network.title": "Keine Verbindung zum Server",
    "err.network.body": "Prüfe die Internetverbindung des Handys und versuch es erneut.",
    "footer.source": "Quellcode",
  },
};
const LANG = (navigator.language || "en").toLowerCase().startsWith("de") ? "de" : "en";
document.documentElement.lang = LANG;

function t(key, vars = {}) {
  let s = I18N[LANG][key] ?? I18N.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

const PLATFORMS = { instagram: "Instagram", facebook: "Facebook" };

// --------------------------------------------------------------------- helpers
const $ = (id) => document.getElementById(id);
const VIEWS = ["home", "work", "done", "error"];
const fileCache = new Map(); // `${job id}/${server file name}` -> File
const cacheKey = (jobId, name) => `${jobId}/${name}`;
let config = { retention_hours: 24, version: "" };
// Every change of view starts a new generation. Code that waited for the server checks that its
// generation is still current, so a late answer for a job the user left changes nothing.
let generation = 0;

function applyStatic() {
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  // Keep the wrapper (e.g. az-alert__icon, az-empty__icon), it sizes and colours the icon.
  document.querySelectorAll("[data-icon]").forEach((el) => { el.replaceChildren(icon(el.dataset.icon)); });
  $("sig-host").textContent = location.host;
}

function show(view) {
  generation += 1;
  VIEWS.forEach((v) => { $(`view-${v}`).hidden = v !== view; });
  hideAlert();
  window.scrollTo({ top: 0 });
}

// Page-wide feedback: the Alert building block (title says what happened).
function showAlert(kind, title, body, { autoHide = false } = {}) {
  const box = $("page-alert");
  const icons = { success: "check-circle", info: "info-circle", danger: "exclamation-circle" };
  box.className = `az-alert az-alert--${kind}`;
  box.setAttribute("role", kind === "danger" ? "alert" : "status");
  box.querySelector(".az-alert__icon").replaceChildren(icon(icons[kind]));
  box.querySelector(".az-alert__title").textContent = title;
  box.querySelector(".az-alert__body").textContent = body;
  box.hidden = false;
  clearTimeout(showAlert.timer);
  if (autoHide) showAlert.timer = setTimeout(hideAlert, 5000);
}

function hideAlert() {
  clearTimeout(showAlert.timer);
  $("page-alert").hidden = true;
}

class ApiError extends Error {
  constructor(code, detail = "") { super(code); this.code = code; this.detail = detail; }
}

// Reload at most once a minute, so a misbehaving proxy cannot cause a reload loop.
function reloadAllowed() {
  try {
    const last = Number(sessionStorage.getItem("sharewerk-reload") || 0);
    if (Date.now() - last < 60000) return false;
    sessionStorage.setItem("sharewerk-reload", String(Date.now()));
    return true;
  } catch {
    return false;
  }
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...options });
  } catch {
    throw new ApiError("network");
  }
  if (response.status === 401) {
    location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
    throw new ApiError("unauthorised");
  }
  // An auth proxy that lost its session answers with its login page instead of JSON.
  const type = response.headers.get("content-type") || "";
  if (!type.includes("application/json")) {
    if (response.ok && reloadAllowed()) location.reload();
    throw new ApiError("network");
  }
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail || {};
    throw new ApiError(detail.code || "internal", detail.message || "");
  }
  return data;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fileUrl = (jobId, name) => `/api/jobs/${jobId}/files/${encodeURIComponent(name)}`;

function count(n, one, many) {
  return n === 1 ? t(one) : t(many, { n });
}

function formatDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : new Intl.DateTimeFormat(LANG, { dateStyle: "long" }).format(d);
}

// "vor 3 Stunden", "3 hours ago"
function relativeTime(seconds) {
  const diff = seconds - Date.now() / 1000;
  const rtf = new Intl.RelativeTimeFormat(LANG, { numeric: "auto" });
  for (const [unit, size] of [["day", 86400], ["hour", 3600], ["minute", 60]]) {
    if (Math.abs(diff) >= size) return rtf.format(Math.round(diff / size), unit);
  }
  return rtf.format(0, "minute");
}

function button(label, iconName, onClick, classes = "az-btn az-btn--secondary az-btn--sm") {
  const b = document.createElement("button");
  b.type = "button";
  b.className = classes;
  if (iconName) b.append(icon(iconName));
  const span = document.createElement("span");
  span.className = "sw-label";
  span.textContent = label;
  b.append(span);
  b.addEventListener("click", onClick);
  return b;
}

// ------------------------------------------------------------------------ home
async function showHome(errorCode, value) {
  show("home");
  const input = $("link-input");
  if (value !== undefined) input.value = value;
  setFieldError(errorCode);
  $("install-alert").hidden = matchMedia("(display-mode: standalone)").matches;
  $("recent-empty-body").textContent = t("recent.emptyBody", { h: config.retention_hours });
  let jobs = [];
  try {
    jobs = await api("/api/jobs");
  } catch { /* the list is optional */ }
  renderRecent(jobs);
}

function setFieldError(code) {
  const input = $("link-input");
  const err = $("link-error");
  if (!code) {
    err.hidden = true;
    input.removeAttribute("aria-invalid");
    return;
  }
  const key = `field.${code}`;
  $("link-error-text").textContent = t(key) === key ? t("field.no_url") : t(key);
  err.hidden = false;
  input.setAttribute("aria-invalid", "true");
}

const STATUS = {
  done: ["az-label az-label--success", "check-circle"],
  error: ["az-label az-label--danger", "exclamation-circle"],
  queued: ["az-label", null],
  running: ["az-label", null],
};

function renderRecent(jobs) {
  $("recent-card").hidden = jobs.length === 0;
  $("recent-empty").hidden = jobs.length !== 0;
  const body = $("recent");
  body.replaceChildren();
  for (const job of jobs) {
    const tr = document.createElement("tr");

    const post = document.createElement("td");
    post.dataset.label = t("recent.post");
    const name = document.createElement("span");
    name.textContent = job.author ? `@${job.author}` : PLATFORMS[job.platform] || job.platform;
    const sub = document.createElement("span");
    sub.className = "az-cell-sub az-mono";
    sub.textContent = job.url;
    const both = document.createElement("span");
    both.append(name, sub);
    post.append(both);

    const status = document.createElement("td");
    status.className = "az-nowrap";
    status.dataset.label = t("recent.status");
    const [cls, iconName] = STATUS[job.status] || STATUS.queued;
    const label = document.createElement("span");
    label.className = cls;
    if (iconName) label.append(icon(iconName));
    label.append(t(`status.${job.status}`));
    status.append(label);

    const time = document.createElement("td");
    time.className = "az-nowrap";
    time.dataset.label = t("recent.time");
    time.textContent = relativeTime(job.created);

    const actions = document.createElement("td");
    actions.className = "az-cell-actions";
    const open = document.createElement("a");
    open.className = "az-btn az-btn--plain az-btn--sm";
    open.href = `/?job=${job.id}`;
    open.setAttribute("aria-label", t("recent.open"));
    open.title = t("recent.open");
    open.append(icon("angle-right"));
    actions.append(open);

    tr.append(post, status, time, actions);
    body.append(tr);
  }
}

$("link-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const value = $("link-input").value.trim();
  if (!value) return setFieldError("no_url");
  startJob({ text: value });
});

// ------------------------------------------------------------------------- job
// What was shared, for display: apps put the link into url, text or only the title.
const sharedText = (body) => body.url || body.text || body.title || "";

async function startJob(body) {
  show("work");
  const mine = generation;
  $("work-source").textContent = sharedText(body);
  renderProgress({ status: "queued", stage: "queued", queue_position: 0 });
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (mine !== generation) return;
    history.replaceState(null, "", `/?job=${job.id}`);
    await poll(job.id);
  } catch (error) {
    if (mine !== generation || error.code === "unauthorised") return;
    history.replaceState(null, "", "/");
    if (error.code.startsWith("network")) return renderError({ error_code: "network", url: "" });
    // The link was fine, the server could not store the job: an error page whose retry sends
    // the original fields again.
    if (error.code === "storage_failed") return renderError({ error_code: error.code }, body);
    showHome(error.code, sharedText(body));
  }
}

async function poll(jobId) {
  show("work");
  const mine = generation;
  let delay = 800;
  for (;;) {
    let job;
    try {
      job = await api(`/api/jobs/${jobId}`);
    } catch (error) {
      if (mine !== generation || error.code === "unauthorised") return;
      if (error.code === "network") { await sleep(3000); continue; }
      return renderError({ error_code: error.code, url: "" });
    }
    if (mine !== generation) return; // the user went on to something else
    $("work-source").textContent = job.url;
    if (job.status === "done") return renderDone(job);
    if (job.status === "error") return renderError(job);
    renderProgress(job);
    await sleep(delay);
    delay = Math.min(2000, delay + 200);
  }
}

function renderProgress(job) {
  const stage = job.status === "queued" ? "queued" : job.stage;
  $("work-step").textContent = t(`step.${stage}`) === `step.${stage}` ? t("step.processing") : t(`step.${stage}`);
  const q = $("queue-info");
  q.hidden = !(job.queue_position > 0);
  if (job.queue_position > 0) q.textContent = t("queue", { n: job.queue_position });
}

// ---------------------------------------------------------------------- result
async function renderDone(job) {
  show("done");
  const mine = generation;
  const r = job.result;
  const m = r.meta;
  const platform = PLATFORMS[m.platform] || m.platform;

  $("result-title").textContent = m.author ? t("done.titleAuthor", { a: m.author })
    : m.author_name ? t("done.titleName", { a: m.author_name })
    : t("done.titlePlain", { p: platform });
  const contents = [];
  if (r.counts.images) contents.push(count(r.counts.images, "done.image", "done.images"));
  if (r.counts.videos) contents.push(count(r.counts.videos, "done.video", "done.videos"));
  $("result-meta").textContent = [platform, m.date ? formatDate(m.date) : "", contents.join(", ")]
    .filter(Boolean).join(" · ");
  $("result-link").href = m.url;

  const primary = r.packs.compact ? r.packs.compact[0] : r.packs.full[0];
  const pictures = r.counts.pictures;
  $("pack-summary").textContent = !pictures ? t("done.packText")
    : r.packs.compact ? t("done.packSheets", { n: pictures, s: primary.length - 1 })
    : pictures === 1 ? t("done.packPicture") : t("done.packPictures", { n: pictures });

  const canShareFiles = typeof navigator.canShare === "function";
  const shareButton = $("btn-share");
  setLoading(shareButton, false); // a job left while loading must not leave the button busy
  shareButton.hidden = !canShareFiles;
  shareButton.onclick = () => shareBatch(shareButton, job, primary);
  $("downloads").hidden = true;
  if (!canShareFiles) showDownloads(job, primary);

  renderThumbs(job, r.packs.full.flat().filter((n) => n !== "post.txt"));

  // Second card: single pictures and original files.
  const more = $("more-actions");
  more.replaceChildren();
  if (canShareFiles) {
    if (r.packs.compact) {
      r.packs.full.forEach((batch, i, all) => {
        const label = all.length === 1 ? t("more.single") : t("more.singlePart", { i: i + 1, n: all.length });
        const b = button(label, "share-alt", () => shareBatch(b, job, batch));
        more.append(b);
      });
    }
    (r.packs.originals || []).forEach((batch, i, all) => {
      const label = all.length === 1 ? t("more.original") : t("more.originalPart", { i: i + 1, n: all.length });
      const b = button(label, "share-alt", () => shareBatch(b, job, batch));
      more.append(b);
    });
  }
  $("more-card").hidden = more.children.length === 0;

  // Text that goes with the pack
  let text = "";
  try {
    const res = await fetch(fileUrl(job.id, primary[0]), { credentials: "same-origin" });
    text = await res.text();
  } catch { /* preview is optional */ }
  if (mine !== generation) return; // the user left this job meanwhile
  $("result-text").textContent = text;
  $("btn-copy").onclick = async () => {
    try {
      await navigator.clipboard.writeText(text);
      showAlert("success", t("alert.copiedTitle"), t("alert.copiedBody"), { autoHide: true });
    } catch {
      showAlert("danger", t("alert.copyFailedTitle"), t("alert.copyFailedBody"));
    }
  };

  // Load the files now, so a tap shares immediately (the tap must still count as user activation).
  if (canShareFiles) {
    setLoading(shareButton, true);
    try { await loadFiles(job, primary); } catch { /* retried on tap */ }
    if (mine !== generation) return;
    setLoading(shareButton, false);
  }
}

function videoTime(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0)); // same as fmt_time() on the server
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// Image preview: the Thumbnails building block of the Azentrius Design System.
function renderThumbs(job, names) {
  const list = $("thumbs");
  list.replaceChildren();
  list.setAttribute("aria-label", t("thumbs.label"));
  for (const name of names) {
    const meta = job.result.files[name];
    const frame = meta.kind === "frame";
    const time = videoTime(meta.time);
    const li = document.createElement("li");
    li.className = "az-thumb";
    const img = document.createElement("img");
    img.className = "az-thumb__image";
    img.src = fileUrl(job.id, name);
    img.loading = "lazy";
    img.alt = frame ? t("thumbs.altFrame", { n: meta.number, t: time }) : t("thumbs.altImage", { n: meta.number, i: meta.item });
    const caption = document.createElement("span");
    caption.className = "az-thumb__caption";
    const number = document.createElement("span");
    number.className = "az-thumb__number";
    number.textContent = String(meta.number);
    caption.append(number, ` · ${frame ? t("thumbs.frame", { t: time }) : t("thumbs.image")}`);
    li.append(img, caption);
    list.append(li);
  }
  list.hidden = names.length === 0;
}

function setLoading(btn, loading) {
  const label = btn.querySelector(".sw-label");
  if (loading) {
    btn.dataset.label = label.textContent;
    label.textContent = t("done.loading");
  } else if (btn.dataset.label) {
    label.textContent = btn.dataset.label;
  }
  btn.disabled = loading;
}

// Files are cached per job. A file that arrives after the user left its job is dropped.
async function loadFiles(job, names) {
  const mine = generation;
  const files = [];
  for (const name of names) {
    const key = cacheKey(job.id, name);
    if (!fileCache.has(key)) {
      const meta = job.result.files[name];
      const res = await fetch(fileUrl(job.id, name), { credentials: "same-origin" });
      if (!res.ok) throw new ApiError("file_not_found");
      const blob = await res.blob();
      if (mine !== generation) throw new ApiError("left");
      fileCache.set(key, new File([blob], meta.name, { type: meta.type }));
    }
    files.push(fileCache.get(key));
  }
  return files;
}

async function shareBatch(btn, job, names) {
  const mine = generation;
  hideAlert();
  let files;
  try {
    if (!names.every((n) => fileCache.has(cacheKey(job.id, n)))) setLoading(btn, true);
    files = await loadFiles(job, names);
  } catch {
    if (mine !== generation) return;
    setLoading(btn, false);
    return showAlert("danger", t("alert.loadFailedTitle"), t("alert.loadFailedBody"));
  }
  setLoading(btn, false);

  if (!navigator.canShare({ files })) {
    showDownloads(job, names);
    return showAlert("danger", t("alert.cannotShareTitle"), t("alert.cannotShareBody"));
  }
  try {
    await navigator.share({ files });
  } catch (error) {
    if (error.name === "AbortError") return; // the share sheet was closed
    if (error.name === "NotAllowedError") {
      // Loading took too long, the tap no longer counts as user activation.
      return showAlert("info", t("alert.tapAgainTitle"), t("alert.tapAgainBody"));
    }
    showDownloads(job, names);
    showAlert("danger", t("alert.cannotShareTitle"), t("alert.cannotShareBody"));
  }
}

function showDownloads(job, names) {
  const list = $("downloads");
  list.replaceChildren();
  const intro = document.createElement("li");
  intro.textContent = t("done.downloadIntro");
  list.append(intro);
  for (const name of names) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = fileUrl(job.id, name);
    a.download = job.result.files[name].name;
    a.textContent = job.result.files[name].name;
    li.append(a);
    list.append(li);
  }
  list.hidden = false;
}

// ----------------------------------------------------------------------- error
// request: what "Prepare post again" submits again; by default the job's link.
function renderError(job, request = { url: job.url }) {
  show("error");
  let code = job.error_code || "internal";
  if (t(`err.${code}.title`) === `err.${code}.title`) code = "internal";
  $("error-title").textContent = t(`err.${code}.title`);
  $("error-text").textContent = t(`err.${code}.body`, { h: config.retention_hours });
  const source = sharedText(request);
  $("error-source-line").hidden = !source;
  $("error-source").textContent = source;
  $("error-details-line").hidden = !job.error_detail;
  $("error-details").textContent = job.error_detail || "";
  $("error-actions").hidden = !source;
  $("btn-retry").onclick = () => startJob({ ...request, force: true });
}

$("btn-new").addEventListener("click", () => { history.replaceState(null, "", "/"); fileCache.clear(); showHome(undefined, ""); });
$("btn-error-new").addEventListener("click", () => { history.replaceState(null, "", "/"); showHome(undefined, ""); });

// ------------------------------------------------------------------------ boot
async function boot() {
  applyStatic();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  try {
    config = { ...config, ...(await api("/api/config")) };
    if (config.version) $("sig-product").textContent = `Sharewerk ${config.version}`;
  } catch { /* defaults are fine */ }
  const params = new URLSearchParams(location.search);
  const shared = ["title", "text", "url"].some((k) => params.get(k));
  if (shared) {
    startJob({ title: params.get("title"), text: params.get("text"), url: params.get("url") });
  } else if (params.get("job")) {
    poll(params.get("job"));
  } else {
    showHome();
  }
}

boot();
