// SPDX-License-Identifier: Apache-2.0
// Texts of the extension, English and German. "du", as in all own Azentrius apps; buttons are verb
// plus object. Name and description for the Chrome menus are in _locales/.

export const TEXT = {
  en: {
    "alert.noServerTitle": "Set the Sharewerk address",
    "alert.noServerBody": "Enter the address of your Sharewerk server. The extension sends cookies only there.",
    "alert.permissionTitle": "Access to Sharewerk is missing",
    "alert.permissionBody": "Save the Sharewerk address again in the settings and allow the access.",
    "alert.loginTitle": "Sharewerk asks for a login",
    "alert.loginBody": "Sign in to Sharewerk in this browser. The extension then sends the cookies by itself.",
    "alert.offlineTitle": "Sharewerk is not reachable",
    "alert.offlineBody": "The extension tries again every hour and after your next login.",
    "alert.errorTitle": "Sharewerk answered with an error",
    "alert.errorBody": "Error code: {code}",
    "action.openSettings": "Open settings",
    "action.openSharewerk": "Open Sharewerk",
    "action.send": "Send cookies",
    "action.useAccount": "Use account",
    "action.logIn": "Log in to {platform}",
    "status.sent": "Sent to Sharewerk on {time}.",
    "status.never": "Not sent to Sharewerk yet.",
    "status.loggedOut": "Not logged in to {platform} in this browser.",
    "status.confirm": "Logged in to {platform} with the account ID {account}. Should Sharewerk use this account?",
    "status.confirmHint": "Use a secondary account, not your main one.",
    "status.waiting": "Waiting for Sharewerk. The cookies go out as soon as it is reachable and you are signed in.",
    "status.error": "Sharewerk refused the cookies ({code}).",
    "state.ok": "Valid",
    "state.expired": "Expired",
    "state.unknown": "Not tried yet",
    "state.missing": "None on Sharewerk",
    "state.fromFile": "Sharewerk uses the cookie file on the server for {platform}.",
    "options.desc": "Settings of the browser extension",
    "server.title": "Sharewerk server",
    "server.desc": "The extension sends the cookies of Instagram and Facebook to this address only, with your login at Sharewerk in this browser.",
    "server.label": "Sharewerk address",
    "server.help": "The address you open Sharewerk with, e.g. https://sharewerk.example.com.",
    "server.invalid": "Enter an address that starts with https://.",
    "server.denied": "Without access to this address the extension cannot send anything. Save it again and allow the access.",
    "server.save": "Save address",
    "server.savedTitle": "Address saved",
    "server.savedBody": "The extension now sends the cookies of the platforms you are logged in to. Confirm the account once in the extension's menu.",
    "sent.title": "Cookies on Sharewerk",
    "sent.desc": "What Sharewerk has for each platform. Deleting the cookies also forgets the confirmed account.",
    "sent.platform": "Platform",
    "sent.state": "State",
    "sent.actions": "Actions",
    "sent.delete": "Delete cookies",
    "delete.title": "Delete the {platform} cookies?",
    "delete.body": "Sharewerk deletes the {platform} cookies this extension sent. Posts that need a login fail until you confirm an account again.",
    "delete.confirm": "Delete cookies",
    "delete.cancel": "Cancel",
    "delete.close": "Close",
    "deleted.title": "Cookies deleted",
    "deleted.body": "Sharewerk no longer has the {platform} cookies of this extension.",
    "deleteFailed.title": "Could not delete the cookies",
    "footer.settings": "Settings",
    "footer.source": "Source code",
  },
  de: {
    "alert.noServerTitle": "Sharewerk-Adresse festlegen",
    "alert.noServerBody": "Trag die Adresse deines Sharewerk-Servers ein. Die Erweiterung sendet Cookies nur dorthin.",
    "alert.permissionTitle": "Zugriff auf Sharewerk fehlt",
    "alert.permissionBody": "Speichere die Sharewerk-Adresse in den Einstellungen noch einmal und erlaube den Zugriff.",
    "alert.loginTitle": "Sharewerk verlangt eine Anmeldung",
    "alert.loginBody": "Melde dich in diesem Browser bei Sharewerk an. Danach sendet die Erweiterung die Cookies von selbst.",
    "alert.offlineTitle": "Sharewerk ist nicht erreichbar",
    "alert.offlineBody": "Die Erweiterung versucht es stündlich und nach deiner nächsten Anmeldung erneut.",
    "alert.errorTitle": "Sharewerk hat mit einem Fehler geantwortet",
    "alert.errorBody": "Fehlercode: {code}",
    "action.openSettings": "Einstellungen öffnen",
    "action.openSharewerk": "Sharewerk öffnen",
    "action.send": "Cookies senden",
    "action.useAccount": "Konto verwenden",
    "action.logIn": "Bei {platform} anmelden",
    "status.sent": "Am {time} an Sharewerk gesendet.",
    "status.never": "Noch nicht an Sharewerk gesendet.",
    "status.loggedOut": "In diesem Browser nicht bei {platform} angemeldet.",
    "status.confirm": "Bei {platform} mit der Konto-ID {account} angemeldet. Soll Sharewerk dieses Konto verwenden?",
    "status.confirmHint": "Nimm ein Zweitkonto, nicht dein Hauptkonto.",
    "status.waiting": "Wartet auf Sharewerk. Die Cookies gehen raus, sobald Sharewerk erreichbar ist und du angemeldet bist.",
    "status.error": "Sharewerk hat die Cookies abgelehnt ({code}).",
    "state.ok": "Gültig",
    "state.expired": "Abgelaufen",
    "state.unknown": "Noch nicht geprüft",
    "state.missing": "Keine auf Sharewerk",
    "state.fromFile": "Sharewerk nutzt für {platform} die Cookie-Datei auf dem Server.",
    "options.desc": "Einstellungen der Browser-Erweiterung",
    "server.title": "Sharewerk-Server",
    "server.desc": "Die Erweiterung sendet die Cookies von Instagram und Facebook nur an diese Adresse, mit deiner Anmeldung bei Sharewerk in diesem Browser.",
    "server.label": "Sharewerk-Adresse",
    "server.help": "Die Adresse, unter der du Sharewerk öffnest, z. B. https://sharewerk.example.com.",
    "server.invalid": "Gib eine Adresse ein, die mit https:// beginnt.",
    "server.denied": "Ohne Zugriff auf diese Adresse kann die Erweiterung nichts senden. Speichere sie noch einmal und erlaube den Zugriff.",
    "server.save": "Adresse speichern",
    "server.savedTitle": "Adresse gespeichert",
    "server.savedBody": "Die Erweiterung sendet jetzt die Cookies der Plattformen, bei denen du angemeldet bist. Bestätige das Konto einmal im Menü der Erweiterung.",
    "sent.title": "Cookies auf Sharewerk",
    "sent.desc": "Was Sharewerk je Plattform hat. Beim Löschen der Cookies vergisst die Erweiterung auch das bestätigte Konto.",
    "sent.platform": "Plattform",
    "sent.state": "Zustand",
    "sent.actions": "Aktionen",
    "sent.delete": "Cookies löschen",
    "delete.title": "{platform}-Cookies löschen?",
    "delete.body": "Sharewerk löscht die {platform}-Cookies, die diese Erweiterung gesendet hat. Beiträge, die eine Anmeldung brauchen, scheitern, bis du wieder ein Konto bestätigst.",
    "delete.confirm": "Cookies löschen",
    "delete.cancel": "Abbrechen",
    "delete.close": "Schließen",
    "deleted.title": "Cookies gelöscht",
    "deleted.body": "Sharewerk hat die {platform}-Cookies dieser Erweiterung nicht mehr.",
    "deleteFailed.title": "Cookies konnten nicht gelöscht werden",
    "footer.settings": "Einstellungen",
    "footer.source": "Quellcode",
  },
};

export function language(tag) {
  return String(tag || "en").toLowerCase().startsWith("de") ? "de" : "en";
}

export const LANG = language(globalThis.navigator?.language);

export function t(key, vars = {}, lang = LANG) {
  let s = TEXT[lang][key] ?? TEXT.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

/** A point in time as the page language writes it, e.g. "25 Oct 2026, 14:03". */
export function when(ms, lang = LANG) {
  const locale = lang === "de" ? "de-DE" : "en-GB";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(ms));
}
