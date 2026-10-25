// SPDX-License-Identifier: Apache-2.0
// The extension's menu: per platform what was sent and what Sharewerk says about it, with the
// action that is due (confirm the account, log in, send again).
import { browserApi } from "./browser.js";
import { LANG, t, when } from "./i18n.js";
import {
  PLATFORMS, confirm, getServer, loadPlatform, resendLost, serverStates, sync, syncAll, updateBadge,
} from "./sync.js";

const api = browserApi();
const $ = (id) => document.getElementById(id);
const { icon } = globalThis; // icons.js

// The Sharewerk state of a platform's cookies as a label (Azentrius Design System, Label).
const LABELS = {
  ok: "az-label az-label--success",
  expired: "az-label az-label--danger",
  unknown: "az-label az-label--info",
  missing: "az-label",
};

// What keeps the cookies from Sharewerk, as an alert with the action that helps.
const PROBLEMS = {
  no_server: ["info", "info-circle", "alert.noServerTitle", "alert.noServerBody", "action.openSettings", openSettings],
  permission: ["warning", "exclamation-circle", "alert.permissionTitle", "alert.permissionBody", "action.openSettings", openSettings],
  login: ["warning", "exclamation-circle", "alert.loginTitle", "alert.loginBody", "action.openSharewerk", openSharewerk],
  offline: ["danger", "exclamation-circle", "alert.offlineTitle", "alert.offlineBody", null, null],
  error: ["danger", "exclamation-circle", "alert.errorTitle", "alert.errorBody", null, null],
};

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(className, text, onClick) {
  const node = el("button", className, text);
  node.type = "button";
  node.addEventListener("click", onClick);
  return node;
}

function openSettings() {
  chrome.runtime.openOptionsPage();
  window.close();
}

async function openSharewerk() {
  const server = await getServer(api);
  if (server) chrome.tabs.create({ url: server });
  window.close();
}

function openTab(url) {
  chrome.tabs.create({ url });
  window.close();
}

function showProblem(result) {
  const box = $("alert");
  const problem = PROBLEMS[result.status];
  if (!problem) {
    box.hidden = true;
    return;
  }
  const [kind, iconName, title, body, action, onAction] = problem;
  box.className = `az-alert az-alert--${kind}`;
  box.setAttribute("role", kind === "danger" ? "alert" : "status");
  box.querySelector(".az-alert__icon").replaceChildren(icon(iconName));
  box.querySelector(".az-alert__title").textContent = t(title);
  box.querySelector(".az-alert__body").textContent = t(body, { code: result.error || "" });
  const actionButton = $("alert-action");
  actionButton.parentElement.hidden = !action;
  if (action) {
    actionButton.textContent = t(action);
    actionButton.onclick = onAction;
  }
  box.hidden = false;
}

// Buttons are disabled while an action runs; the menu is drawn again afterwards.
async function act(task) {
  document.querySelectorAll("#platforms button").forEach((b) => { b.disabled = true; });
  try {
    await task();
  } finally {
    await render();
  }
}

function card(id, local, server) {
  const spec = PLATFORMS[id];
  const vars = { platform: spec.name };
  const section = el("section", "az-card");
  section.dataset.platform = id;
  const header = el("div", "az-card__header");
  header.append(el("h2", "az-card__title", spec.name));
  if (server && LABELS[server.state]) header.append(el("span", LABELS[server.state], t(`state.${server.state}`)));
  const body = el("div", "az-card__body sx-stack");
  const actions = el("div", "az-card__actions");
  const send = () => button("az-btn az-btn--secondary az-btn--sm", t("action.send"), () => act(() => sync(api, id, { manual: true })));

  switch (local.status) {
    case "confirm":
      body.append(el("p", "", t("status.confirm", { ...vars, account: local.pending || "?" })));
      body.append(el("p", "az-meta", t("status.confirmHint")));
      // The account shown here is the one confirmed, or nothing if the login changed meanwhile.
      actions.append(button("az-btn az-btn--primary az-btn--sm", t("action.useAccount"), () => act(() => confirm(api, id, local.pending))));
      break;
    case "logged_out":
      body.append(el("p", "", t("status.loggedOut", vars)));
      actions.append(button("az-btn az-btn--secondary az-btn--sm", t("action.logIn", vars), () => openTab(spec.home)));
      break;
    case "error":
      body.append(el("p", "", t("status.error", { code: local.error || "?" })));
      actions.append(send());
      break;
    case "login":
    case "offline":
      body.append(el("p", "", t("status.waiting")));
      break;
    default: // sent, nothing yet, or no address or permission (the alert above says what to do)
      body.append(el("p", "", local.sentAt ? t("status.sent", { time: when(local.sentAt) }) : t("status.never")));
      if (local.account && local.status === "sent") actions.append(send());
  }
  if (server?.source === "file") body.append(el("p", "az-meta", t("state.fromFile", vars)));
  if (actions.children.length) body.append(actions);
  section.append(header, body);
  return section;
}

async function render() {
  const states = await serverStates(api);
  showProblem(states);
  const cards = [];
  for (const id of Object.keys(PLATFORMS)) cards.push(card(id, await loadPlatform(api, id), states.platforms?.[id]));
  $("platforms").replaceChildren(...cards);
  await updateBadge(api);
  return states;
}

document.documentElement.lang = LANG;
document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
$("open-settings").addEventListener("click", openSettings);

// Draw what is known at once, then catch up on anything waiting (e.g. you just signed in to
// Sharewerk, or it lost cookies it had) and draw again.
render()
  .then((states) => (states.status === "ok" ? resendLost(api, states.platforms) : null))
  .then(() => syncAll(api))
  .then(render);
