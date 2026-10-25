// SPDX-License-Identifier: Apache-2.0
// Service worker: sends the cookies of a platform to Sharewerk when you log in there, sends what
// waited when you sign in to Sharewerk and every hour, and keeps the badge current.
import { browserApi } from "./browser.js";
import {
  PLATFORMS, getServer, loadPlatform, loginChange, platformOf, resendLost, serverLogin, serverStates, sync,
  syncAll, updateBadge,
} from "./sync.js";

const api = browserApi();
const RETRY = "sharewerk-retry";
const SERVER_RETRY_GAP = 60 * 1000; // a proxy that sets a cookie on every answer must not cause a loop
const timers = new Map();
let lastServerRetry = 0;

function warn(error) {
  console.warn("Sharewerk:", error.message);
}

// A login sets several cookies within a moment: act once, when they are all there.
function soon(key, task) {
  clearTimeout(timers.get(key));
  timers.set(key, setTimeout(() => {
    timers.delete(key);
    task().then(() => updateBadge(api)).catch(warn);
  }, 2000));
}

async function waitingForLogin() {
  for (const id of Object.keys(PLATFORMS)) {
    if ((await loadPlatform(api, id)).status === "login") return true;
  }
  return false;
}

chrome.cookies.onChanged.addListener(async (change) => {
  const id = loginChange(change);
  if (id) {
    soon(id, () => sync(api, id));
    return;
  }
  if (platformOf(change.cookie?.domain)) return; // one of the many other cookies of a platform
  if (!serverLogin(change, await getServer(api))) return;
  // You signed in to Sharewerk: send what waited for that, at most once a minute.
  if (Date.now() - lastServerRetry < SERVER_RETRY_GAP || !(await waitingForLogin())) return;
  lastServerRetry = Date.now();
  soon("server", () => syncAll(api));
});

// Also send again what Sharewerk lost (deleted elsewhere, a new data volume).
async function catchUp() {
  const states = await serverStates(api);
  if (states.status === "ok") await resendLost(api, states.platforms);
  await syncAll(api);
  await updateBadge(api);
}

async function start() {
  await chrome.alarms.create(RETRY, { periodInMinutes: 60 });
  await catchUp();
}

chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  await start().catch(warn);
  if (reason === "install" && !(await getServer(api))) chrome.runtime.openOptionsPage();
});

chrome.runtime.onStartup.addListener(() => {
  start().catch(warn);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === RETRY) catchUp().catch(warn);
});
