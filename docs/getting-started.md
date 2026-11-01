# Getting started

Run your own Sharewerk in about half an hour, without knowing Docker or web servers. You need:

- an **Android phone with Chrome** (iPhones cannot share to a web app),
- **Chrome on a computer**, for the browser extension that sends the cookies,
- a **secondary Instagram account**, not your main one (see [Cookies](../README.md#cookies) for why),
- and a place where Sharewerk runs all the time. There are two ways; pick one:

| | A: own server with a domain | B: at home with Tailscale |
|---|---|---|
| Runs on | a small rented server (about 5 € a month) | a computer at home that is always on, e.g. a Raspberry Pi 4 or 5 |
| Address | `https://sharewerk.your-domain.com` | `https://sharewerk.your-tailnet.ts.net` |
| You also need | a domain | a free Tailscale account, and the Tailscale app on your phone |
| Reachable from | anywhere | only your own devices in Tailscale |

The machine needs 2 CPU cores and 4 GB of memory, Linux (Debian, Ubuntu or Raspberry Pi OS, 64-bit), and about 5 GB of free disk space.

## A: own server with a domain

1. **Rent a server** with Debian or Ubuntu at any provider. Note its IP address.
2. **Point the domain to it.** At your domain provider, add a DNS record of type `A` for the name you want (for example `sharewerk.your-domain.com`) with the server's IP address. If the server also has an IPv6 address, add an `AAAA` record. It can take a few minutes until the name works.
3. **Open the ports** 80 and 443 in the provider's firewall, if it has one. Caddy, which Sharewerk brings along, needs them to get the HTTPS certificate.
4. **Log in to the server** (`ssh root@<IP address>`) and install Docker and Git:

   ```bash
   curl -fsSL https://get.docker.com | sh
   apt-get install -y git
   ```

5. **Get Sharewerk and set it up**, with your domain:

   ```bash
   git clone https://github.com/Azentrius/sharewerk.git
   cd sharewerk
   ./setup.sh --domain sharewerk.your-domain.com
   ```

   `setup.sh` creates the access token, writes the settings to `.env`, downloads Sharewerk and starts it. At the end it shows the address and the **access token**. Keep the token; it is also in `.env`.

Continue with [Install the app](#install-the-app).

## B: at home with Tailscale

1. **Create a Tailscale account** at [tailscale.com](https://tailscale.com) (free for personal use).
2. In the Tailscale admin console, under **DNS**, switch on **MagicDNS** and **HTTPS Certificates**.
3. Under **Settings › Keys**, create an **auth key**. It starts with `tskey-auth-`.
4. **Install Docker and Git** on the computer at home (64-bit Linux):

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo apt-get install -y git
   ```

5. **Get Sharewerk and set it up**, with your auth key:

   ```bash
   git clone https://github.com/Azentrius/sharewerk.git
   cd sharewerk
   sudo ./setup.sh --tailscale tskey-auth-...
   ```

   At the end `setup.sh` shows the **access token**; keep it, it is also in `.env`. Sharewerk appears as the machine `sharewerk` in the Tailscale admin console, with the address `https://sharewerk.<your-tailnet>.ts.net`.
6. **Install the Tailscale app** on your phone and sign in with the same account.

## Install the app

1. On the phone, open your Sharewerk address in **Chrome**. The first visit can take a minute while the HTTPS certificate is made.
2. Enter the **access token** once. The phone stays signed in.
3. Chrome menu ⋮ › **Install app** (on some versions: "Add to home screen").
4. Sharewerk is now in the share menu: in Instagram tap **Share** › **Share to…**, pick **Sharewerk**.

## Add the cookies

Instagram shows almost nothing to visitors who are not logged in. The Sharewerk browser extension sends the cookies of your secondary account to your Sharewerk:

1. On the computer, create a **new Chrome profile** just for this (Chrome menu › profile icon › Add).
2. In that profile, install the **Sharewerk extension**, see [Browser extension](../README.md#browser-extension-chrome).
3. The extension's settings open: enter your Sharewerk address and allow the access.
4. In the same profile, open your Sharewerk address and sign in with the access token.
5. Log in to Instagram with your **secondary account** (and to Facebook, if you want).
6. Click the Sharewerk icon in the toolbar and confirm the account with **Use account**.
7. Close the profile without logging out. Open it again only when Sharewerk says that Instagram asks for a login; log in there again, and the extension sends the new cookies by itself.

Done: share a post from Instagram to Sharewerk.

## Updating

Sharewerk is rebuilt every week with the newest downloaders. To update, in the `sharewerk` folder (add `sudo` for B):

```bash
docker compose pull && docker compose up -d
```

## When something does not work

| What you see | What to do |
|---|---|
| The address does not open (A) | Check that the DNS record points to the server (`ping sharewerk.your-domain.com`) and that ports 80 and 443 are open; then `docker compose restart caddy`. |
| The address does not open (B) | Check that the phone is connected in the Tailscale app, and that MagicDNS and HTTPS Certificates are on. |
| Token lost | `grep SHAREWERK_AUTH_TOKEN .env` in the `sharewerk` folder. |
| "Instagram asks for a login" | Log in to Instagram again in the Chrome profile of step "Add the cookies". |
| Anything else | `docker compose logs --tail 50` shows what happened; the [troubleshooting table](../README.md#troubleshooting) explains the messages. |
