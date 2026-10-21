// SPDX-License-Identifier: Apache-2.0
// The installed PWA after a server update: the service worker of the old version still holds
// the old scripts in its cache while the page itself comes fresh from the server. The page is
// rendered by the real app (Python), the scripts run in a small DOM built from that HTML,
// including the real icon code; the old service worker runs in its own sandbox.
// Run with: node --test tests/js/pwa-update.test.mjs  (PYTHON=<python with the app's dependencies>)
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const REPO = new URL("../../", import.meta.url);
const ORIGIN = "https://sharewerk.test";
const OLD = new URL("fixtures/release-0.1.1/", import.meta.url); // 1134f2e, release 0.1.1

// The page "/" exactly as the server answers it.
function servedPage() {
  const script = [
    "import sys, tempfile",
    "from pathlib import Path",
    "from fastapi.testclient import TestClient",
    "from app.config import Settings",
    "from app.main import create_app",
    "d = Path(tempfile.mkdtemp())",
    "s = Settings(auth_mode='none', data_dir=d, cookies_file=d / 'c', gallery_dl_config=d / 'g', whisper_model='off')",
    "with TestClient(create_app(s)) as c:",
    "    sys.stdout.write(c.get('/').text)",
  ].join("\n");
  return execFileSync(process.env.PYTHON || "python", ["-c", script], { cwd: REPO, encoding: "utf8" });
}

// ------------------------------------------------------------------ a small DOM
const VOID = new Set(["meta", "link", "input", "br", "img", "hr", "source", "path"]);

class Node {
  constructor(tag, attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.attrs = { ...attrs };
    this.children = [];
    this.listeners = {};
    this.parent = null;
    this.value = attrs.value || "";
    this._text = "";
  }
  get id() { return this.attrs.id || ""; }
  get hidden() { return "hidden" in this.attrs; }
  set hidden(on) { if (on) this.attrs.hidden = ""; else delete this.attrs.hidden; }
  get className() { return this.attrs.class || ""; }
  set className(v) { this.attrs.class = v; }
  get dataset() {
    const data = {};
    for (const [k, v] of Object.entries(this.attrs)) {
      if (k.startsWith("data-")) data[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = v;
    }
    return new Proxy(data, { set: (t, k, v) => { this.attrs[`data-${String(k)}`] = String(v); t[k] = v; return true; } });
  }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); }
  set textContent(v) { this.children = []; this._text = String(v); }
  getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; }
  setAttribute(name, v) { this.attrs[name] = String(v); }
  removeAttribute(name) { delete this.attrs[name]; }
  hasAttribute(name) { return name in this.attrs; }
  append(...nodes) {
    for (const n of nodes) {
      if (typeof n === "string") this._text += n;
      else { n.parent = this; this.children.push(n); }
    }
  }
  replaceChildren(...nodes) { this.children = []; this._text = ""; this.append(...nodes); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  focus() {}
  matches(sel) {
    if (sel.startsWith("[")) return sel.slice(1, -1) in this.attrs;
    if (sel.startsWith(".")) return this.className.split(/\s+/).includes(sel.slice(1));
    if (sel.startsWith("#")) return this.id === sel.slice(1);
    return this.tagName === sel.toUpperCase();
  }
  querySelectorAll(sel) {
    const found = [];
    for (const c of this.children) {
      if (c.matches(sel)) found.push(c);
      found.push(...c.querySelectorAll(sel));
    }
    return found;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}

function parse(html) {
  const root = new Node("#document");
  const stack = [root];
  const tag = /<!--[\s\S]*?-->|<!doctype[^>]*>|<\/([a-z0-9-]+)\s*>|<([a-z0-9-]+)((?:\s+[^\s=>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>/gi;
  for (const m of html.matchAll(tag)) {
    if (m[1]) {
      const name = m[1].toUpperCase();
      while (stack.length > 1 && stack.pop().tagName !== name);
      continue;
    }
    if (!m[2]) continue; // comment or doctype
    const attrs = {};
    for (const a of (m[3] || "").matchAll(/([^\s=>/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) {
      attrs[a[1].toLowerCase()] = a[2] ?? a[3] ?? a[4] ?? "";
    }
    const node = new Node(m[2], attrs);
    stack.at(-1).append(node);
    if (!VOID.has(m[2].toLowerCase()) && !m[4]) stack.push(node);
  }
  return root;
}

// ------------------------------------------------------- network and responses
function response(body, type, status = 200, url = "") {
  return {
    ok: status < 400, status, url,
    headers: { get: (n) => (n.toLowerCase() === "content-type" ? type : null) },
    text: async () => body,
    json: async () => JSON.parse(body),
    clone() { return response(body, type, status, url); },
  };
}

// The server: /static/ from `files` (a function name -> text), the API, nothing else.
function server(files, calls) {
  return async (input) => {
    const url = new URL(typeof input === "string" ? input : input.url, ORIGIN);
    calls.push(url.pathname + url.search);
    if (url.pathname.startsWith("/static/")) {
      const text = files(url.pathname.slice("/static/".length));
      return text === null ? response("", "text/plain", 404) : response(text, "text/javascript", 200, url.href);
    }
    if (url.pathname === "/api/config") return response(JSON.stringify({ version: "0.1.1", retention_hours: 24 }), "application/json");
    if (url.pathname === "/api/jobs") return response("[]", "application/json");
    throw new Error(`unexpected request ${url.href}`);
  };
}

const current = (name) => {
  try { return readFileSync(new URL(`app/static/${name}`, REPO), "utf8"); } catch { return null; }
};
const old = (name) => {
  try { return readFileSync(new URL(name, OLD), "utf8"); } catch { return current(name); }
};

// ------------------------------------------------------ the service worker
function cacheStorage() {
  const stores = new Map();
  const open = (name) => {
    if (!stores.has(name)) {
      const entries = new Map();
      stores.set(name, {
        entries,
        match: async (req) => entries.get(new URL(req.url || req, ORIGIN).href)?.clone(),
        put: async (req, res) => { entries.set(new URL(req.url || req, ORIGIN).href, res); },
        keys: async () => [...entries.keys()].map((url) => ({ url })),
        delete: async (req) => entries.delete(new URL(req.url || req, ORIGIN).href),
      });
    }
    return stores.get(name);
  };
  return {
    stores,
    open: async (name) => open(name),
    keys: async () => [...stores.keys()],
    delete: async (name) => stores.delete(name),
  };
}

// installed: true when the worker is already installed and active (no install/activate again).
async function installWorker(source, caches, network, { installed = false } = {}) {
  const listeners = {};
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); },
    skipWaiting: async () => {},
    clients: { claim: async () => {} },
  };
  const context = { self, caches, URL, Promise, console };
  context.fetch = network;
  // cache.addAll() resolves relative URLs against the worker's location, like a browser.
  const realOpen = caches.open;
  context.caches = {
    ...caches,
    open: async (name) => {
      const cache = await realOpen(name);
      cache.addAll ||= async (urls) => {
        for (const u of urls) await cache.put({ url: u }, await network(new URL(u, ORIGIN).href));
      };
      return cache;
    },
  };
  vm.createContext(context);
  vm.runInContext(source, context, { filename: "sw.js" });
  for (const phase of installed ? [] : ["install", "activate"]) {
    const waits = [];
    for (const fn of listeners[phase] || []) fn({ waitUntil: (p) => waits.push(p) });
    await Promise.all(waits);
  }
  // A fetch through the worker: its answer, or the network when it does not respond.
  return async (url) => {
    let answer = null;
    const event = { request: { url: new URL(url, ORIGIN).href, method: "GET" }, respondWith: (p) => { answer = p; } };
    for (const fn of listeners.fetch || []) fn(event);
    return answer ? answer : network(event.request.url);
  };
}

// ------------------------------------------------------------- the page itself
async function openPage(html, load, network) {
  const document = parse(html);
  const htmlNode = document.querySelector("html") || document;
  const byId = (id) => document.querySelectorAll(`#${id}`)[0] || null;
  const errors = [];
  const context = {
    console, setTimeout, clearTimeout, URLSearchParams, Intl, URL,
    fetch: network,
    document: {
      documentElement: htmlNode,
      getElementById: byId,
      querySelectorAll: (sel) => document.querySelectorAll(sel),
      querySelector: (sel) => document.querySelector(sel),
      createElement: (tag) => new Node(tag),
      createElementNS: (_, tag) => new Node(tag),
      addEventListener() {},
    },
    navigator: { language: "de-DE", serviceWorker: { register: async () => ({}) } },
    location: { host: "sharewerk.test", pathname: "/", search: "", href: `${ORIGIN}/`, reload() {} },
    history: { replaceState() {} },
    sessionStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    scrollTo() {},
  };
  context.window = context;
  vm.createContext(context);
  const onError = (e) => errors.push(e);
  process.on("unhandledRejection", onError);
  // Scripts in document order (theme.js, then the deferred icons.js and app.js).
  for (const script of document.querySelectorAll("script")) {
    const src = script.getAttribute("src");
    if (!src) continue;
    const res = await load(src);
    try {
      vm.runInContext(await res.text(), context, { filename: src });
    } catch (e) {
      errors.push(e);
    }
  }
  for (let i = 0; i < 50; i += 1) await new Promise((r) => setImmediate(r));
  process.off("unhandledRejection", onError);
  return { document, byId, errors };
}

function assertStarted(page, calls) {
  assert.deepEqual(page.errors.map(String), []);
  assert.equal(page.byId("view-home").hidden, false, "the start view is shown");
  for (const view of ["view-work", "view-done", "view-error"]) assert.equal(page.byId(view).hidden, true);
  const icons = page.document.querySelectorAll("[data-icon]");
  assert.ok(icons.length > 0);
  for (const el of icons) assert.equal(el.children[0]?.tagName, "SVG", `icon ${el.getAttribute("data-icon")} drawn`);
  assert.ok(calls.includes("/api/config") && calls.includes("/api/jobs"), "the app asked the server");
}

test("a fresh start without a service worker", async () => {
  const calls = [];
  const network = server(current, calls);
  const page = await openPage(servedPage(), network, network);
  assertStarted(page, calls);
});

test("the first open after an update, while the worker of 0.1.1 still has its cache", async () => {
  // Before the update: the 0.1.1 worker installed and cached the 0.1.1 files.
  const caches = cacheStorage();
  const before = [];
  const oldWorker = await installWorker(old("sw.js"), caches, server(old, before));
  for (const name of ["theme.js", "icons.js", "app.js"]) await oldWorker(`/static/${name}`);

  // The server runs the new version now; the page comes fresh, the old worker is still in charge.
  const calls = [];
  const network = server(current, calls);
  const stillOld = await installWorker(old("sw.js"), caches, network, { installed: true });
  const page = await openPage(servedPage(), stillOld, network);
  assertStarted(page, calls);

  // Then the new worker takes over (sw.js is fetched without cache): the next open works too,
  // and no copy of 0.1.1 is left in a cache.
  const next = [];
  const newWorker = await installWorker(current("sw.js"), caches, server(current, next));
  const again = await openPage(servedPage(), newWorker, server(current, next));
  assertStarted(again, next);
  for (const store of caches.stores.values()) {
    for (const [url, res] of store.entries) {
      const name = new URL(url).pathname.replace("/static/", "");
      const text = await res.text();
      if (old(name) !== current(name)) assert.notEqual(text, old(name), `${name} from 0.1.1 still cached`);
    }
  }
});
