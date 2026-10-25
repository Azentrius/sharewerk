// SPDX-License-Identifier: Apache-2.0
// The chrome APIs that sync.js works with (the tests hand it fakes instead).
export function browserApi() {
  return {
    cookies: chrome.cookies,
    storage: chrome.storage,
    permissions: chrome.permissions,
    action: chrome.action,
    fetch: (...args) => fetch(...args),
  };
}
