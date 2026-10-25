// SPDX-License-Identifier: Apache-2.0
// What the extension does, apart from the browser glue: which cookies belong to which platform,
// when they go to the Sharewerk server, and what the popup shows. background.js, popup.js and
// options.js call it with the real chrome API, the tests (tests/js/extension.test.mjs) with a fake.
//
// `api` holds cookies, storage, permissions, action (chrome.*) and fetch.

// The platforms of app/cookies.py, with the same login cookies. A new platform needs an entry
// there too, and a host permission in manifest.json.
export const PLATFORMS = {
  instagram: {
    name: "Instagram",
    domain: "instagram.com",
    session: ["sessionid"], // exist only while an account is logged in
    account: "ds_user_id", // the numeric id of the logged-in account
    accountInSession: "sessionid", // starts with that id (<id>%3A...): the id of the session sent
    home: "https://www.instagram.com/",
  },
  facebook: {
    name: "Facebook",
    domain: "facebook.com",
    session: ["c_user", "xs"],
    account: "c_user",
    home: "https://www.facebook.com/",
  },
};

// Every request to Sharewerk carries it; the server refuses cookie uploads without it.
export const CLIENT_HEADER = "X-Sharewerk-Client";

// Statuses that need you (or the server) before cookies can go out again.
const TROUBLE = new Set(["no_server", "permission", "login", "offline", "error"]);

export function belongs(domain, base) {
  const d = String(domain || "").toLowerCase().replace(/^\.+/, "");
  return d === base || d.endsWith(`.${base}`);
}

export function platformOf(domain) {
  return Object.keys(PLATFORMS).find((id) => belongs(domain, PLATFORMS[id].domain)) || null;
}

/** The platform whose login a cookie change belongs to (a login cookie was set), or null. */
export function loginChange(change) {
  if (!change || change.removed || !change.cookie) return null;
  const id = platformOf(change.cookie.domain);
  return id && PLATFORMS[id].session.includes(change.cookie.name) ? id : null;
}

/** True when a cookie was set for the Sharewerk server: you signed in there (Pomerium or the
    app's own login), so cookies that waited for that login can go out now. */
export function serverLogin(change, server) {
  if (!change || change.removed || !change.cookie || !server) return false;
  let host;
  try {
    host = new URL(server).hostname;
  } catch {
    return false;
  }
  // A cookie of domain D reaches host H when H is D or a subdomain of a domain cookie's D.
  return belongs(host, String(change.cookie.domain || "").toLowerCase().replace(/^\.+/, ""));
}

/** The origin of a Sharewerk address, or "" if it is none: https, or http on this computer only. */
export function serverOrigin(input) {
  let url;
  try {
    url = new URL(String(input || "").trim());
  } catch {
    return "";
  }
  const local = ["localhost", "127.0.0.1"].includes(url.hostname); // as in optional_host_permissions
  if (url.username || url.password) return "";
  if (url.protocol !== "https:" && !(url.protocol === "http:" && local)) return "";
  return url.origin;
}

export const originPattern = (origin) => `${origin}/*`;

// ------------------------------------------------------------------- storage

export async function getServer(api) {
  return (await api.storage.local.get("server")).server || "";
}

export async function setServer(api, origin) {
  await api.storage.local.set({ server: origin });
}

/** What the extension knows about a platform: the confirmed account, the fingerprint of the
    login it sent last (sent, sentAt), the status of the last attempt, and an account waiting for
    your confirmation (pending). One key per platform, so two platforms never overwrite each other. */
export async function loadPlatform(api, id) {
  const key = `platform:${id}`;
  return (await api.storage.local.get(key))[key] || {};
}

async function savePlatform(api, id, changes) {
  const state = { ...(await loadPlatform(api, id)), ...changes };
  await api.storage.local.set({ [`platform:${id}`]: state });
  return state;
}

// ------------------------------------------------------------------- cookies

async function digest(text) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

function decoded(text) {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

/** The login of a platform in this browser: its cookies, the account and a fingerprint of the
    login cookies (a new login or session changes it), or null when no account is logged in. A
    login without an account id counts as none: only an account that can be told apart from
    others is ever confirmed and sent. */
export async function readLogin(api, id) {
  const spec = PLATFORMS[id];
  const all = await api.cookies.getAll({ domain: spec.domain });
  const cookies = all.filter((c) => belongs(c.domain, spec.domain) && !c.partitionKey);
  const value = (name) => cookies.find((c) => c.name === name)?.value;
  if (!spec.session.every((name) => value(name))) return null;
  const inSession = spec.accountInSession ? decoded(value(spec.accountInSession)).split(":")[0] : "";
  const account = /^\d+$/.test(inSession) ? inSession : value(spec.account) || "";
  if (!account) return null;
  return { cookies, account, fingerprint: await digest(spec.session.map(value).join("\n")) };
}

// The fields the server writes into its cookies.txt.
const pick = ({ domain, name, value, path, secure, httpOnly, hostOnly, expirationDate }) =>
  ({ domain, name, value, path, secure, httpOnly, hostOnly, expirationDate });

/** A request to Sharewerk with the browser's login there (Pomerium or the app's own). A redirect
    or 401 means that login is missing; it is never followed. */
async function request(api, server, method, path, body) {
  let response;
  try {
    response = await api.fetch(`${server}${path}`, {
      method,
      credentials: "include",
      redirect: "manual",
      cache: "no-store",
      headers: { [CLIENT_HEADER]: "extension", ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    return { status: "offline" };
  }
  if (response.type === "opaqueredirect" || response.status === 401 || (response.status >= 300 && response.status < 400)) {
    return { status: "login" };
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) return { status: "error", error: data?.detail?.code || `http_${response.status}` };
  if (data === null) return { status: "error", error: "not_sharewerk" };
  return { status: "ok", data };
}

async function reachable(api) {
  const server = await getServer(api);
  if (!server) return { status: "no_server" };
  if (!(await api.permissions.contains({ origins: [originPattern(server)] }))) return { status: "permission" };
  return { status: "ok", server };
}

// ---------------------------------------------------------------------- sync

/**
 * Send the cookies of platform `id` to Sharewerk when they are new (a login, a new session, a new
 * Sharewerk address) or when `manual`. Only for the account you confirmed: another account waits
 * for confirm(). Returns the platform's state.
 */
export async function sync(api, id, { manual = false } = {}) {
  const saved = await loadPlatform(api, id);
  const target = await reachable(api);
  if (target.status !== "ok") return savePlatform(api, id, { status: target.status, error: "" });
  const login = await readLogin(api, id);
  if (!login) return savePlatform(api, id, { status: "logged_out", error: "", pending: "" });
  if (login.account !== saved.account) return savePlatform(api, id, { status: "confirm", error: "", pending: login.account });
  const unchanged = saved.status === "sent" && saved.sent === login.fingerprint && saved.sentTo === target.server;
  if (!manual && unchanged) return saved;

  const result = await request(api, target.server, "PUT", `/api/cookies/${id}`, { cookies: login.cookies.map(pick) });
  if (result.status !== "ok") return savePlatform(api, id, { status: result.status, error: result.error || "" });
  return savePlatform(api, id, {
    status: "sent", error: "", sent: login.fingerprint, sentTo: target.server, sentAt: Date.now(), pending: "",
  });
}

/** Every platform, e.g. after a start, a login at Sharewerk, or the hourly retry. */
export async function syncAll(api) {
  const states = {};
  for (const id of Object.keys(PLATFORMS)) states[id] = await sync(api, id);
  return states;
}

/** You confirmed account `shown`, the one the popup showed: from now on its cookies go to
    Sharewerk. Nothing is confirmed unless it is still the account waiting and logged in. */
export async function confirm(api, id, shown) {
  const saved = await loadPlatform(api, id);
  const login = await readLogin(api, id);
  if (!login || !shown || saved.status !== "confirm" || saved.pending !== shown || login.account !== shown) {
    return sync(api, id); // the login changed after the popup showed it: ask again
  }
  await savePlatform(api, id, { account: shown, pending: "" });
  return sync(api, id, { manual: true });
}

/** Platforms whose cookies Sharewerk no longer has from this extension (deleted elsewhere, a new
    data volume): forget that they were sent, so the next sync sends them again. */
export async function resendLost(api, platforms) {
  const lost = [];
  for (const id of Object.keys(PLATFORMS)) {
    const local = await loadPlatform(api, id);
    if (local.status === "sent" && platforms?.[id] && platforms[id].source !== "extension") {
      await savePlatform(api, id, { sent: "" });
      lost.push(id);
    }
  }
  return lost;
}

/** Delete the cookies of platform `id` on Sharewerk and forget the confirmed account, so the
    next login asks again. Returns { status, error } of the request. */
export async function forget(api, id) {
  const target = await reachable(api);
  if (target.status !== "ok") return { status: target.status };
  const result = await request(api, target.server, "DELETE", `/api/cookies/${id}`);
  if (result.status === "ok" || result.error === "cookies_not_found") {
    await savePlatform(api, id, { account: "", sent: "", sentTo: "", sentAt: 0, status: "", error: "", pending: "" });
    return { status: "ok" };
  }
  return result;
}

/** What Sharewerk says about the cookies of every platform (GET /api/cookies):
    { status: "ok", platforms: { instagram: { state, source, updated }, ... } }, or why not. */
export async function serverStates(api) {
  const target = await reachable(api);
  if (target.status !== "ok") return { status: target.status };
  const result = await request(api, target.server, "GET", "/api/cookies");
  if (result.status !== "ok") return result;
  return { status: "ok", platforms: result.data.platforms || {} };
}

// --------------------------------------------------------------------- badge

/** "!" when something keeps the cookies from Sharewerk, "?" when an account waits for your
    confirmation, "" when all is well. */
export function badgeText(states) {
  const list = Object.values(states);
  if (list.some((s) => TROUBLE.has(s.status))) return "!";
  if (list.some((s) => s.status === "confirm")) return "?";
  return "";
}

export async function updateBadge(api) {
  const states = {};
  for (const id of Object.keys(PLATFORMS)) states[id] = await loadPlatform(api, id);
  const text = badgeText(states);
  // Brand gold on brand ink (Azentrius Design System), as the app sign.
  await api.action.setBadgeBackgroundColor({ color: "#C8A96E" });
  await api.action.setBadgeTextColor({ color: "#0A0A0F" });
  await api.action.setBadgeText({ text });
  return text;
}
