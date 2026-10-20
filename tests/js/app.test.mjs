// SPDX-License-Identifier: Apache-2.0
// app/static/app.js in a Node sandbox: a minimal DOM, a scripted fetch() and navigator.share().
// Run with: node --test tests/js/app.test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const SOURCE = readFileSync(new URL("../../app/static/app.js", import.meta.url), "utf8");

class Element {
  constructor(id = "") {
    this.id = id;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.parts = new Map();
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.className = "";
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  querySelector(selector) {
    if (!this.parts.has(selector)) this.parts.set(selector, new Element());
    return this.parts.get(selector);
  }
  querySelectorAll() { return []; }
  click() {
    for (const listener of this.listeners.click || []) listener({ preventDefault() {} });
    return this.onclick ? this.onclick() : undefined;
  }
}

function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

const fileUrl = (jobId, name) => `/api/jobs/${jobId}/files/${encodeURIComponent(name)}`;

// A finished job with a text file and one picture. Every file's content names its job.
function doneJob(id) {
  const url = `https://www.instagram.com/p/${id}/`;
  return {
    id, url, platform: "instagram", status: "done", stage: "done", queue_position: 0,
    error_code: "", error_detail: "",
    result: {
      meta: { platform: "instagram", url, author: `author${id}`, author_name: "", caption: "", date: "", title: "" },
      counts: { images: 1, videos: 0, pictures: 1 },
      files: {
        "post.txt": { name: `instagram-${id}.txt`, type: "text/plain", size: 10 },
        "01.jpg": { name: `instagram-${id}-01.jpg`, type: "image/jpeg", size: 10,
          label: "image 1", number: 1, kind: "image", item: 1, time: null },
      },
      packs: { full: [["post.txt", "01.jpg"]], compact: null, originals: [] },
      transcript_preview: "", tool: "fake", notes: [],
    },
  };
}

function response(body, type, status = 200) {
  return {
    ok: status < 400,
    status,
    headers: { get: (name) => (name.toLowerCase() === "content-type" ? type : null) },
    json: async () => JSON.parse(body),
    text: async () => body,
    blob: async () => new Blob([body], { type }),
  };
}

// jobs: finished jobs the server knows; created: the answer to POST /api/jobs as [status, body];
// language: the browser language.
function loadApp(jobs, { created, language = "en" } = {}) {
  const elements = new Map();
  const requests = [];
  const holds = [];
  const shared = [];
  const copied = [];
  const posted = []; // bodies of POST /api/jobs

  async function fetch(url, options = {}) {
    requests.push(url);
    const nth = requests.filter((u) => u === url).length;
    const hold = holds.find((h) => h.url === url && h.nth === nth);
    if (hold) await hold.gate.promise;
    if (url === "/api/jobs" && options.method === "POST") {
      posted.push(JSON.parse(options.body));
      const [status, body] = created;
      return response(JSON.stringify(body), "application/json", status);
    }
    if (url === "/api/config") return response(JSON.stringify({ version: "0.1.0", retention_hours: 24 }), "application/json");
    if (url === "/api/jobs") return response("[]", "application/json");
    for (const job of Object.values(jobs)) {
      if (url === `/api/jobs/${job.id}`) return response(JSON.stringify(job), "application/json");
      for (const name of Object.keys(job.result.files)) {
        if (url === fileUrl(job.id, name)) return response(`${job.id}:${name}`, job.result.files[name].type);
      }
    }
    throw new Error(`unexpected request ${url}`);
  }

  const context = {
    console, setTimeout, clearTimeout, setImmediate, Blob, File, URLSearchParams, fetch,
    icon: () => new Element(),
    document: {
      documentElement: {},
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, new Element(id));
        return elements.get(id);
      },
      createElement: () => new Element(),
      querySelectorAll: () => [],
    },
    navigator: {
      language,
      canShare: () => true,
      share: async ({ files }) => { shared.push(files); },
      clipboard: { writeText: async (text) => { copied.push(text); } },
    },
    location: { host: "sharewerk.test", pathname: "/", search: "", href: "/", reload() {} },
    history: { replaceState() {} },
    sessionStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false }),
    scrollTo() {},
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SOURCE, context, { filename: "app.js" });

  return {
    element: (id) => context.document.getElementById(id),
    run: (code) => vm.runInContext(code, context),
    shared,
    copied,
    posted,
    // Answers the nth request to a URL only when the returned function is called.
    hold(url, nth = 1) {
      const gate = deferred();
      holds.push({ url, nth, gate });
      return gate.resolve;
    },
    async settle() {
      for (let i = 0; i < 50; i += 1) await new Promise((r) => setImmediate(r));
    },
  };
}

async function namesAndContents(files) {
  return Promise.all(files.map(async (f) => [f.name, await f.text()]));
}

test("a late file of a left job does not end up in the next job's share", async () => {
  const app = loadApp({ A: doneJob("A"), B: doneJob("B") });
  await app.settle();

  // Job A is ready; its files are preloaded for sharing. The second request for A's post.txt
  // (the first is the text preview) hangs.
  const releaseA = app.hold(fileUrl("A", "post.txt"), 2);
  app.run('poll("A")');
  await app.settle();

  // "Prepare another post" and job B, whose files load completely.
  app.element("btn-new").click();
  await app.settle();
  app.run('poll("B")');
  await app.settle();

  releaseA(); // only now A's answer arrives
  await app.settle();

  await app.element("btn-share").onclick();
  await app.settle();
  assert.equal(app.shared.length, 1);
  assert.deepEqual(await namesAndContents(app.shared[0]), [
    ["instagram-B.txt", "B:post.txt"],
    ["instagram-B-01.jpg", "B:01.jpg"],
  ]);
});

test("a late text preview of a left job does not replace the text on screen", async () => {
  const app = loadApp({ A: doneJob("A"), B: doneJob("B") });
  await app.settle();

  const releaseA = app.hold(fileUrl("A", "post.txt"), 1); // A's text preview hangs
  app.run('poll("A")');
  await app.settle();
  app.element("btn-new").click();
  await app.settle();
  app.run('poll("B")');
  await app.settle();
  assert.equal(app.element("result-text").textContent, "B:post.txt");

  releaseA();
  await app.settle();

  assert.equal(app.element("result-text").textContent, "B:post.txt");
  assert.equal(app.element("btn-share").disabled, false);
  await app.element("btn-copy").onclick();
  assert.deepEqual(app.copied, ["B:post.txt"]);
  await app.element("btn-share").onclick();
  await app.settle();
  assert.deepEqual((await namesAndContents(app.shared[0])).map(([name]) => name), ["instagram-B.txt", "instagram-B-01.jpg"]);
});

test("a job the server cannot save is shown as a storage error, not as an invalid link", async () => {
  const link = "https://www.instagram.com/p/A/";
  const app = loadApp({}, { created: [503, { detail: { code: "storage_failed", message: "No space left on device" } }] });
  await app.settle();
  app.run(`startJob({ url: ${JSON.stringify(link)} })`);
  await app.settle();

  assert.equal(app.element("view-error").hidden, false);
  assert.equal(app.element("view-home").hidden, true);
  assert.equal(app.element("link-error").hidden, true);
  assert.equal(app.element("error-title").textContent, app.run('t("err.storage_failed.title")'));
  assert.equal(app.element("error-source").textContent, link);
  assert.equal(app.element("error-actions").hidden, false); // "Prepare post again"
});

test("the retry after a storage error resends every field of the original share", async () => {
  // Some apps put the link only into the title of a share.
  const share = { title: "Look at this https://www.instagram.com/p/T/", text: null, url: null };
  const app = loadApp({}, { created: [503, { detail: { code: "storage_failed", message: "No space left on device" } }] });
  await app.settle();
  app.run(`startJob(${JSON.stringify(share)})`);
  await app.settle();

  assert.equal(app.element("view-error").hidden, false);
  assert.equal(app.element("error-source-line").hidden, false);
  assert.equal(app.element("error-source").textContent, share.title);
  assert.equal(app.element("error-actions").hidden, false);

  app.element("btn-retry").click();
  await app.settle();
  assert.equal(app.posted.length, 2);
  assert.deepEqual(app.posted[1], { ...share, force: true });
});

test("a job waiting for the Instagram pause says why", async () => {
  for (const language of ["en", "de"]) {
    const app = loadApp({}, { language });
    await app.settle();
    app.run('renderProgress({ status: "running", stage: "waiting", queue_position: 0 })');
    const text = app.element("work-step").textContent;
    assert.equal(text, app.run('I18N[LANG]["step.waiting"]'));
    assert.notEqual(text, app.run('t("step.processing")'));
  }
});

test("files of the job on screen are loaded once and shared from the cache", async () => {
  const app = loadApp({ A: doneJob("A") });
  await app.settle();
  app.run('poll("A")');
  await app.settle();

  await app.element("btn-share").onclick();
  await app.element("btn-share").onclick();
  await app.settle();
  assert.equal(app.shared.length, 2);
  assert.ok(app.shared[1].every((file, i) => file === app.shared[0][i]), "the second share reuses the cached files");
  assert.deepEqual(await namesAndContents(app.shared[1]), [
    ["instagram-A.txt", "A:post.txt"],
    ["instagram-A-01.jpg", "A:01.jpg"],
  ]);
});
