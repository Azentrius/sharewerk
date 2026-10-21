// SPDX-License-Identifier: Apache-2.0
// Azentrius Design System: own apps follow the device setting,
// "Azentrius dunkel" in dark mode, "Azentrius hell" otherwise.
// Loaded before the stylesheets so the page never flashes in the wrong theme.
(function () {
  var dark = window.matchMedia("(prefers-color-scheme: dark)");
  function apply() {
    document.documentElement.setAttribute("data-theme", dark.matches ? "azentrius-dunkel" : "azentrius-hell");
  }
  dark.addEventListener("change", apply);
  apply();
})();
