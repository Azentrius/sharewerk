# Chrome Web Store

Everything for the listing of the browser extension, unlisted (installable through the link in the README, not found by the store's search). Texts in English (default) and German.

## Before the first upload

1. Create a developer account at the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole) with the Azentrius Google account (one-time fee of 5 USD), verify the contact email and switch on 2-step verification.
2. Under **Account**, declare the trader status. As a company, Azentrius is a trader: the store shows its address, email and phone number to users in the EU.

## Package

Upload `sharewerk-extension-X.Y.Z.zip` from the [latest release](https://github.com/Azentrius/sharewerk/releases/latest) as it is: `manifest.json` is at the root of the zip, and the version comes from `app/__init__.py`. Every later upload needs a higher version, so upload the zip of each new release.

## Store listing

| Field | Value |
|---|---|
| Name | Sharewerk (from the manifest) |
| Summary | from the manifest (`_locales/<lang>/messages.json`, "description") |
| Category | Tools |
| Language | English; add German |
| Store icon | [`chrome-web-store/store-icon-128.png`](chrome-web-store/store-icon-128.png) (96 px sign, 16 px transparent margin) |
| Screenshots | [`chrome-web-store/`](chrome-web-store/) `screenshot-1-en.png` to `screenshot-3-en.png`, for German `screenshot-1-de.png` to `screenshot-3-de.png` (1280 × 800) |
| Small promo tile | [`chrome-web-store/promo-small.png`](chrome-web-store/promo-small.png) (440 × 280) |
| Homepage URL | https://azentrius.com/sharewerk/ |
| Support URL | https://github.com/Azentrius/sharewerk/issues |

### Description (English)

```text
Sharewerk turns Instagram and Facebook posts into share-ready packs on your own server: every carousel image, key frames and a transcript of videos, and the caption as text. This extension keeps your Sharewerk server logged in to Instagram and Facebook.

How it works:
• You run your own Sharewerk server (open source: github.com/Azentrius/sharewerk) and enter its address in the extension's settings.
• In a Chrome profile of its own, log in to Instagram or Facebook with a secondary account and confirm that account once in the extension's menu.
• From then on the extension sends that account's cookies to your server whenever you log in again, and only to your server. Another account in the same browser is never sent without asking.

What it does not do: it reads no other sites and no browsing history, shows no ads, and sends nothing to Azentrius or anyone else. The menu shows what was sent and when; the settings page deletes the cookies from your server.

You need your own Sharewerk server; without one, the extension has nothing to do. Use a secondary account: automated access is against Meta's terms of use.
```

### Description (German)

```text
Sharewerk macht aus Instagram- und Facebook-Beiträgen teilbare Pakete auf deinem eigenen Server: jedes Bild eines Karussells, Standbilder und ein Transkript von Videos und den Beitragstext. Diese Erweiterung hält deinen Sharewerk-Server bei Instagram und Facebook angemeldet.

So funktioniert es:
• Du betreibst deinen eigenen Sharewerk-Server (Open Source: github.com/Azentrius/sharewerk) und trägst seine Adresse in den Einstellungen der Erweiterung ein.
• In einem eigenen Chrome-Profil meldest du dich mit einem Zweitkonto bei Instagram oder Facebook an und bestätigst dieses Konto einmal im Menü der Erweiterung.
• Ab dann sendet die Erweiterung die Cookies dieses Kontos an deinen Server, sobald du dich neu anmeldest, und nur an deinen Server. Ein anderes Konto im selben Browser wird nie ohne Rückfrage gesendet.

Was sie nicht tut: Sie liest keine anderen Seiten und keinen Browserverlauf, zeigt keine Werbung und sendet nichts an Azentrius oder andere. Das Menü zeigt, was wann gesendet wurde; die Einstellungsseite löscht die Cookies wieder von deinem Server.

Du brauchst deinen eigenen Sharewerk-Server; ohne ihn hat die Erweiterung nichts zu tun. Nimm ein Zweitkonto: Automatisierter Zugriff verstößt gegen die Nutzungsbedingungen von Meta.
```

## Privacy practices

**Single purpose**

```text
Send the login cookies of Instagram and Facebook from this browser to the user's own Sharewerk server, so that it can download the posts the user shares to it.
```

**Permission justifications**

| Permission | Justification |
|---|---|
| `cookies` | Reads the cookies of instagram.com and facebook.com (the login of the account the user confirmed) to send them to the user's own Sharewerk server. Without them the server cannot download posts that need a login. |
| `storage` | Keeps the address of the user's Sharewerk server, the confirmed account per platform, and when its login was last sent. |
| `alarms` | Tries again once an hour when the cookies could not be sent, e.g. while the server was unreachable or the login at Sharewerk had expired. |
| Host permissions `https://*.instagram.com/*`, `https://*.facebook.com/*` | Needed to read the cookies of these two sites. The extension does not access their pages. |
| Optional host permissions `https://*/*`, `http://localhost/*`, `http://127.0.0.1/*` | The address of the user's own Sharewerk server is known only after installation. When the user saves it in the settings, the extension asks for permission for exactly that one origin and sends only there. localhost and 127.0.0.1 are for a server on the same computer. |

**Remote code:** No, I am not using remote code.

**Data usage**

- Collected: **Authentication information** (the Instagram and Facebook cookies, sent only to the server the user configured). Nothing else.
- Certify all three statements: not sold to third parties, not used or transferred for purposes unrelated to the single purpose, not used to determine creditworthiness or for lending.

**Privacy policy URL:** https://github.com/Azentrius/sharewerk/blob/main/PRIVACY.md

## Distribution

- Visibility: **Unlisted**
- Regions: all
- Pricing: free

## After the approval

Send the item's store link; it goes into the README ([Browser extension](../README.md#browser-extension-chrome)) and [docs/getting-started.md](getting-started.md) in place of loading the zip in developer mode. Chrome then updates the extension by itself after each new upload.

## How the images are made

- The store icon comes from `scripts/app-icon-sharewerk.py`, like every other icon.
- The screenshots and the promo tile are rendered from the built extension and the design system with `tools/store-images.py`, which needs Chrome or Edge.
