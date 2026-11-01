# Privacy

Sharewerk is software you run yourself: a server, an app on your phone and a browser extension. This page says what each part does with data. Azentrius, who publishes Sharewerk, receives no data from any of them.

## Browser extension

- **What it reads:** the cookies of instagram.com and facebook.com in the Chrome profile it is installed in, and nothing else. It does not read the pages of these or any other sites, your browsing history, or what you type.
- **Where it sends them:** only to the one Sharewerk address you enter in its settings (your own server), over HTTPS, or plain HTTP to a server on the same computer. It sends them only for the Instagram or Facebook account you confirmed in its menu, after you log in there.
- **What it keeps in the browser:** the Sharewerk address and, per platform, the confirmed account ID, a fingerprint (SHA-256) of the login it sent last, when it sent it, and how the last attempt ended. It keeps no cookie values of its own.
- **What it does not do:** no analytics, no ads, no code from the internet, nothing to Azentrius or any third party.
- **Your control:** the menu shows what was sent and when. The settings page deletes the cookies it sent from your server. Removing the extension removes what it keeps in the browser.

## Sharewerk server and app

Whoever runs a Sharewerk server is responsible for it; for your own server, that is you.

- The server keeps the cookies it receives in its data volume, readable by the app's user only, and uses them only to download the posts you share to it. It never writes cookie values to its log.
- It keeps the links you share and the results for 24 hours by default (`SHAREWERK_RETENTION_HOURS`), or until you delete them in the app.
- It contacts Instagram and Facebook to download the posts you share, with the cookies of your account, and Hugging Face when it loads the speech recognition model (the first time to download it).
- The app on your phone talks to your server only. Sharewerk sends no telemetry.

## Contact

Questions: [GitHub issues](https://github.com/Azentrius/sharewerk/issues). Security problems: see [SECURITY.md](SECURITY.md).
