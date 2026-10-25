// SPDX-License-Identifier: Apache-2.0
// The browser extension's logic (extension/sync.js) against a fake chrome API: which cookies go
// to Sharewerk, when, for which account, and what happens when Sharewerk wants a login.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import * as sync from "../../extension/sync.js";
import { TEXT, language, t } from "../../extension/i18n.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const EXTENSION = join(ROOT, "extension");
const SERVER = "https://sharewerk.example.com";

const cookie = (domain, name, value = "v", extra = {}) => ({
  domain, name, value, path: "/", secure: true, httpOnly: true, hostOnly: false, session: false,
  expirationDate: 1893456000, storeId: "0", sameSite: "no_restriction", ...extra,
});
const ig = (name, value) => cookie(".instagram.com", name, value);
const fb = (name, value) => cookie(".facebook.com", name, value);

const json = (status, data) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const OK = () => json(200, { platform: "x", state: "unknown", source: "extension", updated: 1 });
const REDIRECT = () => ({ type: "opaqueredirect", status: 0, ok: false, json: async () => { throw new Error("opaque"); } });

/** A fake of the chrome APIs that sync.js uses; `respond(url, init)` answers fetch. */
function fakeApi({ jar = [], server = SERVER, granted = true, respond = OK } = {}) {
  const values = new Map(server ? [["server", server]] : []);
  const api = {
    jar,
    requests: [],
    badge: {},
    respond,
    granted,
    cookies: {
      getAll: async ({ domain }) => api.jar.filter((c) => sync.belongs(c.domain, domain)).map((c) => ({ ...c })),
    },
    storage: {
      local: {
        get: async (keys) => {
          const list = Array.isArray(keys) ? keys : [keys];
          return Object.fromEntries(list.filter((k) => values.has(k)).map((k) => [k, structuredClone(values.get(k))]));
        },
        set: async (items) => { for (const [k, v] of Object.entries(items)) values.set(k, structuredClone(v)); },
      },
    },
    allowed: [`${SERVER}/*`],
    permissions: { contains: async ({ origins }) => api.granted && origins.every((o) => api.allowed.includes(o)) },
    action: {
      setBadgeText: async ({ text }) => { api.badge.text = text; },
      setBadgeBackgroundColor: async ({ color }) => { api.badge.background = color; },
      setBadgeTextColor: async ({ color }) => { api.badge.color = color; },
    },
    fetch: async (url, init) => {
      api.requests.push({ url, init, body: init.body ? JSON.parse(init.body) : null });
      return api.respond(url, init);
    },
  };
  return api;
}

const INSTAGRAM_LOGIN = () => [ig("sessionid", "s1"), ig("ds_user_id", "111"), ig("csrftoken", "c1")];

// ------------------------------------------------------------------ sending

test("a login is sent only after its account is confirmed, with the cookies of that platform only", async () => {
  const api = fakeApi({
    jar: [
      ...INSTAGRAM_LOGIN(),
      fb("c_user", "999"),
      cookie(".instagram.com", "partitioned", "p", { partitionKey: { topLevelSite: "https://example.net" } }),
    ],
  });

  let state = await sync.sync(api, "instagram");
  assert.equal(state.status, "confirm");
  assert.equal(state.pending, "111");
  assert.equal(api.requests.length, 0);
  assert.equal(await sync.updateBadge(api), "?");

  state = await sync.confirm(api, "instagram", "111");
  assert.equal(state.status, "sent");
  assert.equal(state.account, "111");
  assert.equal(api.requests.length, 1);
  const [{ url, init, body }] = api.requests;
  assert.equal(url, `${SERVER}/api/cookies/instagram`);
  assert.equal(init.method, "PUT");
  assert.equal(init.credentials, "include"); // the browser's login at Sharewerk (Pomerium)
  assert.equal(init.redirect, "manual"); // a login redirect is never followed
  assert.equal(init.headers["X-Sharewerk-Client"], "extension");
  assert.equal(init.headers["Content-Type"], "application/json");
  assert.deepEqual(body.cookies.map((c) => c.name).sort(), ["csrftoken", "ds_user_id", "sessionid"]);
  assert.deepEqual(Object.keys(body.cookies[0]).sort(),
    ["domain", "expirationDate", "hostOnly", "httpOnly", "name", "path", "secure", "value"]);
  assert.equal(await sync.updateBadge(api), "");
});

test("the same login is not sent again, a new session is", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram");
  await sync.confirm(api, "instagram", "111");
  assert.equal(api.requests.length, 1);

  await sync.sync(api, "instagram");
  await sync.syncAll(api);
  assert.equal(api.requests.length, 1);

  api.jar.find((c) => c.name === "csrftoken").value = "c2"; // other cookies change all the time
  await sync.sync(api, "instagram");
  assert.equal(api.requests.length, 1);

  api.jar.find((c) => c.name === "sessionid").value = "s2"; // a new session
  assert.equal((await sync.sync(api, "instagram")).status, "sent");
  assert.equal(api.requests.length, 2);

  await sync.sync(api, "instagram", { manual: true }); // "Send cookies"
  assert.equal(api.requests.length, 3);
});

test("another account in the browser waits for confirmation and is not sent", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram");
  await sync.confirm(api, "instagram", "111");

  api.jar = [ig("sessionid", "main"), ig("ds_user_id", "222")]; // e.g. the main account
  let state = await sync.sync(api, "instagram");
  assert.deepEqual([state.status, state.pending, state.account], ["confirm", "222", "111"]);
  state = await sync.sync(api, "instagram", { manual: true });
  assert.equal(state.status, "confirm");
  assert.equal(api.requests.length, 1);
  assert.equal(await sync.updateBadge(api), "?");
});

test("a confirmation for an account that changed meanwhile asks again", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram"); // the popup shows 111
  api.jar = [ig("sessionid", "other"), ig("ds_user_id", "333")];
  const state = await sync.confirm(api, "instagram", "111");
  assert.deepEqual([state.status, state.pending, state.account], ["confirm", "333", undefined]);
  assert.equal(api.requests.length, 0);
});

test("only the account the popup showed can be confirmed", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram"); // the popup shows 111 ...
  api.jar = [ig("sessionid", "s9"), ig("ds_user_id", "222")];
  await sync.syncAll(api); // ... while a sync in the background notes 222 as waiting
  let state = await sync.confirm(api, "instagram", "111"); // the click on what was shown
  assert.deepEqual([state.status, state.pending, state.account], ["confirm", "222", undefined]);
  state = await sync.confirm(api, "instagram", "");
  assert.equal(state.account, undefined);
  assert.equal(api.requests.length, 0);
});

test("a login without an account id is never confirmed or sent", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram");
  await sync.confirm(api, "instagram", "111");
  api.respond = () => json(200, { platform: "instagram", state: "missing", source: "", updated: null });
  await sync.forget(api, "instagram"); // the confirmed account is now ""

  api.jar = [ig("sessionid", "no-id-in-here")]; // ds_user_id expired, the session lives on
  for (const manual of [false, true]) {
    assert.equal((await sync.sync(api, "instagram", { manual })).status, "logged_out");
  }
  assert.equal((await sync.confirm(api, "instagram", "")).status, "logged_out");
  assert.equal(api.requests.filter((r) => r.init.method === "PUT").length, 1);
});

test("the Instagram account is the one of the session cookie that is sent", async () => {
  const api = fakeApi({ jar: [ig("sessionid", "333%3AabcDEF%3A12%3AAYx"), ig("ds_user_id", "111")] });
  assert.equal((await sync.sync(api, "instagram")).pending, "333");
  api.jar = [ig("sessionid", "not-numbered"), ig("ds_user_id", "111")];
  assert.equal((await sync.sync(api, "instagram")).pending, "111");
});

test("a new Sharewerk address, or cookies Sharewerk lost, get the same login again", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram");
  await sync.confirm(api, "instagram", "111");
  assert.equal(api.requests.length, 1);

  const other = "https://cookies.example.org";
  api.allowed.push(`${other}/*`);
  await sync.setServer(api, other);
  await sync.syncAll(api);
  assert.equal(api.requests.length, 2);
  assert.equal(api.requests[1].url, `${other}/api/cookies/instagram`);

  await sync.syncAll(api);
  assert.equal(api.requests.length, 2);
  // Sharewerk says it has no cookies of this extension (deleted elsewhere, a new volume):
  const lost = await sync.resendLost(api, { instagram: { state: "missing", source: "" }, facebook: { state: "missing", source: "" } });
  assert.deepEqual(lost, ["instagram"]);
  await sync.syncAll(api);
  assert.equal(api.requests.length, 3);
  assert.deepEqual(await sync.resendLost(api, { instagram: { state: "unknown", source: "extension" } }), []);
});

test("Facebook needs both login cookies", async () => {
  const api = fakeApi({ jar: [fb("c_user", "678")] });
  assert.equal((await sync.sync(api, "facebook")).status, "logged_out");
  api.jar.push(fb("xs", "x1"));
  assert.deepEqual(await sync.sync(api, "facebook"), { status: "confirm", error: "", pending: "678" });
});

test("a logged-out browser sends nothing", async () => {
  const api = fakeApi({ jar: [ig("csrftoken", "c"), ig("mid", "m")] });
  const state = await sync.sync(api, "instagram", { manual: true });
  assert.equal(state.status, "logged_out");
  assert.equal(api.requests.length, 0);
});

// ---------------------------------------------------- Sharewerk login and errors

test("a missing Sharewerk login is reported, and the cookies go out once it is there", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN(), respond: REDIRECT });
  await sync.sync(api, "instagram");
  let state = await sync.confirm(api, "instagram", "111");
  assert.equal(state.status, "login");
  assert.equal(await sync.updateBadge(api), "!");

  api.respond = () => json(401, { error: "unauthorised" }); // the app's own token login
  assert.equal((await sync.sync(api, "instagram")).status, "login");

  api.respond = OK; // signed in to Sharewerk: the next attempt sends, without a click
  state = await sync.sync(api, "instagram");
  assert.equal(state.status, "sent");
  assert.equal(api.requests.length, 3);
  assert.equal(await sync.updateBadge(api), "");
});

test("a refused upload keeps the server's error code, an unreachable server is offline", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN(), respond: () => json(422, { detail: { code: "cookie_domain" } }) });
  await sync.sync(api, "instagram");
  let state = await sync.confirm(api, "instagram", "111");
  assert.deepEqual([state.status, state.error], ["error", "cookie_domain"]);

  api.respond = () => new Response("<html>", { status: 200 }); // not Sharewerk's API
  state = await sync.sync(api, "instagram");
  assert.deepEqual([state.status, state.error], ["error", "not_sharewerk"]);

  api.respond = () => { throw new TypeError("Failed to fetch"); };
  state = await sync.sync(api, "instagram");
  assert.equal(state.status, "offline");
  assert.equal(await sync.updateBadge(api), "!");
});

test("without an address or without the permission for it nothing is sent", async () => {
  let api = fakeApi({ jar: INSTAGRAM_LOGIN(), server: "" });
  assert.equal((await sync.sync(api, "instagram")).status, "no_server");
  assert.equal(await sync.updateBadge(api), "!");
  api = fakeApi({ jar: INSTAGRAM_LOGIN(), granted: false });
  assert.equal((await sync.sync(api, "instagram", { manual: true })).status, "permission");
  assert.equal(api.requests.length, 0);
});

test("forgetting deletes the cookies on Sharewerk and the confirmed account", async () => {
  const api = fakeApi({ jar: INSTAGRAM_LOGIN() });
  await sync.sync(api, "instagram");
  await sync.confirm(api, "instagram", "111");
  api.respond = () => json(200, { platform: "instagram", state: "missing", source: "", updated: null });

  assert.deepEqual(await sync.forget(api, "instagram"), { status: "ok" });
  const request = api.requests.at(-1);
  assert.equal(request.init.method, "DELETE");
  assert.equal(request.url, `${SERVER}/api/cookies/instagram`);
  assert.equal(request.init.headers["X-Sharewerk-Client"], "extension");
  assert.equal((await sync.sync(api, "instagram")).status, "confirm"); // asks again
});

test("the server states come from GET /api/cookies", async () => {
  const platforms = { instagram: { state: "ok", source: "extension", updated: 5 }, facebook: { state: "missing", source: "", updated: null } };
  const api = fakeApi({ respond: () => json(200, { platforms }) });
  assert.deepEqual(await sync.serverStates(api), { status: "ok", platforms });
  assert.equal(api.requests[0].init.method, "GET");
  api.respond = REDIRECT;
  assert.deepEqual(await sync.serverStates(api), { status: "login" });
});

// ------------------------------------------------------------------ helpers

test("cookie changes: a set login cookie of a platform, or any cookie for the Sharewerk host", () => {
  assert.equal(sync.loginChange({ removed: false, cookie: ig("sessionid") }), "instagram");
  assert.equal(sync.loginChange({ removed: false, cookie: cookie("www.facebook.com", "xs") }), "facebook");
  assert.equal(sync.loginChange({ removed: true, cookie: ig("sessionid") }), null);
  assert.equal(sync.loginChange({ removed: false, cookie: ig("csrftoken") }), null);
  assert.equal(sync.loginChange({ removed: false, cookie: cookie(".evilinstagram.com", "sessionid") }), null);

  assert.equal(sync.serverLogin({ removed: false, cookie: cookie("sharewerk.example.com", "_pomerium") }, SERVER), true);
  assert.equal(sync.serverLogin({ removed: false, cookie: cookie(".example.com", "_pomerium") }, SERVER), true);
  assert.equal(sync.serverLogin({ removed: false, cookie: cookie("other.example.com", "_pomerium") }, SERVER), false);
  assert.equal(sync.serverLogin({ removed: true, cookie: cookie("sharewerk.example.com", "_pomerium") }, SERVER), false);
  assert.equal(sync.serverLogin({ removed: false, cookie: cookie("sharewerk.example.com", "x") }, ""), false);
});

test("a Sharewerk address is https, or http on this computer only", () => {
  assert.equal(sync.serverOrigin(" https://Sharewerk.example.com/share?x=1 "), "https://sharewerk.example.com");
  assert.equal(sync.serverOrigin("https://sharewerk.example.com:8443"), "https://sharewerk.example.com:8443");
  assert.equal(sync.serverOrigin("http://localhost:8765/"), "http://localhost:8765");
  assert.equal(sync.serverOrigin("http://127.0.0.1:8765"), "http://127.0.0.1:8765");
  assert.equal(sync.serverOrigin("http://[::1]:8765"), ""); // not among the optional permissions
  assert.equal(sync.serverOrigin("http://sharewerk.example.com"), "");
  assert.equal(sync.serverOrigin("https://user:pass@sharewerk.example.com"), "");
  assert.equal(sync.serverOrigin("javascript:alert(1)"), "");
  assert.equal(sync.serverOrigin("sharewerk.example.com"), "");
  assert.equal(sync.serverOrigin(""), "");
});

// ------------------------------------------------------- texts and the manifest

function placeholders(text) {
  return [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
}

test("every text exists in English and German, with the same placeholders", () => {
  assert.deepEqual(Object.keys(TEXT.de).sort(), Object.keys(TEXT.en).sort());
  for (const key of Object.keys(TEXT.en)) {
    assert.deepEqual(placeholders(TEXT.de[key]), placeholders(TEXT.en[key]), key);
  }
  assert.equal(language("de-AT"), "de");
  assert.equal(language("fr"), "en");
  assert.equal(t("action.logIn", { platform: "Instagram" }, "de"), "Bei Instagram anmelden");

  const de = JSON.parse(readFileSync(join(EXTENSION, "_locales", "de", "messages.json"), "utf8"));
  const en = JSON.parse(readFileSync(join(EXTENSION, "_locales", "en", "messages.json"), "utf8"));
  assert.deepEqual(Object.keys(de).sort(), Object.keys(en).sort());
  assert.ok(en.description.message.length <= 132 && de.description.message.length <= 132);
});

test("every text the pages and scripts use exists", () => {
  const used = new Set();
  for (const name of readdirSync(EXTENSION)) {
    if (!/\.(html|js)$/.test(name)) continue;
    const source = readFileSync(join(EXTENSION, name), "utf8");
    for (const m of source.matchAll(/data-i18n="([^"]+)"/g)) used.add(m[1]);
    for (const m of source.matchAll(/\bt\(\s*"([^"]+)"/g)) used.add(m[1]);
    for (const m of source.matchAll(/"((?:alert|action)\.\w+)"/g)) used.add(m[1]);
  }
  for (const state of ["ok", "expired", "unknown", "missing"]) used.add(`state.${state}`);
  const missing = [...used].filter((key) => !(key in TEXT.en));
  assert.deepEqual(missing, []);
});

test("the manifest asks for no more than the extension needs", () => {
  const manifest = JSON.parse(readFileSync(join(EXTENSION, "manifest.json"), "utf8"));
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.permissions, ["cookies", "storage", "alarms"]);
  assert.deepEqual(manifest.host_permissions, ["https://*.instagram.com/*", "https://*.facebook.com/*"]);
  // The Sharewerk address is chosen in the settings and allowed by you then, not at install.
  assert.deepEqual(manifest.optional_host_permissions, ["https://*/*", "http://localhost/*", "http://127.0.0.1/*"]);
  for (const key of ["content_scripts", "externally_connectable", "web_accessible_resources", "content_security_policy", "version"]) {
    assert.equal(key in manifest, false, key);
  }
  const hosts = manifest.host_permissions.map((p) => p.match(/^https:\/\/\*\.([^/]+)\/\*$/)[1]).sort();
  assert.deepEqual(hosts, Object.values(sync.PLATFORMS).map((p) => p.domain).sort());
});

test("the platforms and their login cookies agree with the server (app/cookies.py)", () => {
  const source = readFileSync(join(ROOT, "app", "cookies.py"), "utf8");
  const server = {};
  for (const m of source.matchAll(/"(\w+)": Platform\("([^"]+)", \(([^)]*)\)\)/g)) {
    server[m[1]] = { domain: m[2], session: [...m[3].matchAll(/"([^"]+)"/g)].map((s) => s[1]) };
  }
  const extension = Object.fromEntries(
    Object.entries(sync.PLATFORMS).map(([id, p]) => [id, { domain: p.domain, session: p.session }]),
  );
  assert.deepEqual(extension, server);
});
