// SPDX-License-Identifier: Apache-2.0
// Settings: the Sharewerk address (with the browser's permission to send there) and the cookies
// Sharewerk has from this extension, which can be deleted there.
import { browserApi } from "./browser.js";
import { LANG, t } from "./i18n.js";
import {
  PLATFORMS, forget, getServer, originPattern, serverOrigin, serverStates, setServer, syncAll, updateBadge,
} from "./sync.js";

const api = browserApi();
const $ = (id) => document.getElementById(id);
const { icon } = globalThis; // icons.js

const LABELS = {
  ok: "az-label az-label--success",
  expired: "az-label az-label--danger",
  unknown: "az-label az-label--info",
  missing: "az-label",
};

const PROBLEMS = {
  login: ["warning", "alert.loginTitle", "alert.loginBody"],
  offline: ["danger", "alert.offlineTitle", "alert.offlineBody"],
  error: ["danger", "alert.errorTitle", "alert.errorBody"],
};

function showAlert(kind, title, body) {
  const box = $("alert");
  const icons = { success: "check-circle", info: "info-circle", warning: "exclamation-circle", danger: "exclamation-circle" };
  box.className = `az-alert az-alert--${kind}`;
  box.setAttribute("role", kind === "danger" ? "alert" : "status");
  box.querySelector(".az-alert__icon").replaceChildren(icon(icons[kind]));
  box.querySelector(".az-alert__title").textContent = title;
  box.querySelector(".az-alert__body").textContent = body;
  box.hidden = false;
}

function fieldError(text) {
  $("server-error-text").textContent = text;
  $("server-error").hidden = !text;
  if (text) $("server-input").setAttribute("aria-invalid", "true");
  else $("server-input").removeAttribute("aria-invalid");
}

async function save(event) {
  event.preventDefault();
  fieldError("");
  const origin = serverOrigin($("server-input").value);
  if (!origin) return fieldError(t("server.invalid"));
  // The permission prompt needs the click: it has to be the first thing that waits.
  const granted = await chrome.permissions.request({ origins: [originPattern(origin)] }).catch(() => false);
  if (!granted) return fieldError(t("server.denied"));
  const previous = await getServer(api);
  await setServer(api, origin);
  if (previous && previous !== origin) {
    await chrome.permissions.remove({ origins: [originPattern(previous)] }).catch(() => {});
  }
  $("server-input").value = origin;
  showAlert("success", t("server.savedTitle"), t("server.savedBody"));
  await syncAll(api);
  await updateBadge(api);
  await renderSent();
}

async function renderSent() {
  const states = await serverStates(api);
  const card = $("sent-card");
  if (states.status === "no_server" || states.status === "permission") {
    card.hidden = true;
    return;
  }
  if (states.status !== "ok") {
    const [kind, title, body] = PROBLEMS[states.status];
    showAlert(kind, t(title), t(body, { code: states.error || "" }));
    card.hidden = true;
    return;
  }
  const rows = Object.keys(PLATFORMS).map((id) => {
    const name = PLATFORMS[id].name;
    const info = states.platforms[id] || { state: "missing", source: "" };
    const tr = document.createElement("tr");
    const platform = document.createElement("td");
    platform.dataset.label = t("sent.platform");
    platform.textContent = name;
    const state = document.createElement("td");
    state.dataset.label = t("sent.state");
    const label = document.createElement("span");
    label.className = LABELS[info.state] || "az-label";
    label.textContent = t(`state.${info.state}`);
    state.append(label);
    const actions = document.createElement("td");
    actions.className = "az-cell-actions";
    if (info.source === "extension") {
      // A trash icon in the row; the dialog confirms (Azentrius Design System, Button and Modal).
      const del = document.createElement("button");
      del.type = "button";
      del.className = "az-btn az-btn--plain az-btn--sm";
      del.setAttribute("aria-label", t("sent.delete"));
      del.title = t("sent.delete");
      del.append(icon("trash"));
      del.addEventListener("click", () => askDelete(id, del));
      actions.append(del);
    }
    tr.append(platform, state, actions);
    return tr;
  });
  $("sent").replaceChildren(...rows);
  card.hidden = false;
}

// ---------------------------------------------------------------------- delete
let deleting = null; // { id, opener } while the dialog is open

function askDelete(id, opener) {
  deleting = { id, opener };
  const platform = PLATFORMS[id].name;
  $("delete-title").textContent = t("delete.title", { platform });
  $("delete-text").textContent = t("delete.body", { platform });
  $("delete-close").setAttribute("aria-label", t("delete.close"));
  $("delete-dialog").hidden = false;
  $("delete-cancel").focus();
}

function closeDelete() {
  $("delete-dialog").hidden = true;
  if (deleting) deleting.opener.focus();
  deleting = null;
}

async function confirmDelete() {
  if (!deleting) return;
  const { id } = deleting;
  closeDelete();
  const result = await forget(api, id);
  if (result.status === "ok") {
    showAlert("success", t("deleted.title"), t("deleted.body", { platform: PLATFORMS[id].name }));
  } else {
    showAlert("danger", t("deleteFailed.title"), t("alert.errorBody", { code: result.error || result.status }));
  }
  await updateBadge(api);
  await renderSent();
}

document.documentElement.lang = LANG;
document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
document.querySelectorAll("[data-icon]").forEach((node) => { node.replaceChildren(icon(node.dataset.icon)); });
$("sig-version").textContent = chrome.runtime.getManifest().version;
$("server-form").addEventListener("submit", save);
$("delete-confirm").addEventListener("click", confirmDelete);
$("delete-cancel").addEventListener("click", closeDelete);
$("delete-close").addEventListener("click", closeDelete);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("delete-dialog").hidden) closeDelete();
});

getServer(api).then((server) => {
  $("server-input").value = server;
  return renderSent();
});
