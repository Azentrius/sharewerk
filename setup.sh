#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Sets up Sharewerk on this machine: writes .env with a new access token and the way Sharewerk is
# reached, creates secrets/, and starts it with Docker. Run it in the folder of the repository.
#
#   ./setup.sh                                  asks which way
#   ./setup.sh --domain sharewerk.example.com   own server with a domain (Caddy, Let's Encrypt)
#   ./setup.sh --tailscale tskey-auth-...       at home, in your tailnet (Tailscale)
#
# --no-start only writes the files. Running it again keeps the access token and switches the way.
# Step by step: docs/getting-started.md
set -eu

cd "$(dirname "$0")"

usage() {
	sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//'
	exit "${1:-0}"
}

fail() {
	echo "setup.sh: $*" >&2
	exit 1
}

mode=""
value=""
start=yes
while [ $# -gt 0 ]; do
	case "$1" in
	--domain | --tailscale)
		[ $# -ge 2 ] || usage 1 # a failing shift would end the shell before usage
		mode=${1#--}; value=$2; shift 2 ;;
	--no-start) start=no; shift ;;
	-h | --help) usage 0 ;;
	*) usage 1 ;;
	esac
done

if [ -z "$mode" ]; then
	echo "How should your phone reach Sharewerk?"
	echo "  1  Own server with a domain (e.g. sharewerk.example.com)"
	echo "  2  At home, in your tailnet (Tailscale)"
	printf "Choose 1 or 2: "
	read -r choice
	case "$choice" in
	1) mode=domain; printf "Domain: "; read -r value ;;
	2) mode=tailscale; printf "Tailscale auth key (tskey-auth-...): "; read -r value ;;
	*) fail "please choose 1 or 2" ;;
	esac
fi

# Only characters that cannot break .env, the Caddyfile or a shell line. grep checks each line on its
# own, so a line break would let a second line into .env: refuse it first.
case "$value" in
*"
"* | *"$(printf '\r')"*) fail "the value must be one line" ;;
esac
case "$mode" in
domain)
	echo "$value" | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$' ||
		fail "\"$value\" is not a domain like sharewerk.example.com"
	compose_file=compose.yaml:compose.caddy.yaml
	;;
tailscale)
	echo "$value" | grep -Eq '^tskey-[A-Za-z0-9_-]+$' ||
		fail "the Tailscale auth key starts with tskey- (admin console, Settings, Keys)"
	compose_file=compose.yaml:compose.tailscale.yaml
	;;
esac

# .env holds the access token: readable by you only.
umask 077
[ -f .env ] || cp .env.example .env
chmod 600 .env

# set_var NAME VALUE: replace the line NAME=... in .env, or add it.
set_var() {
	awk -v name="$1" -v value="$2" '
		index($0, name "=") == 1 { print name "=" value; done = 1; next }
		{ print }
		END { if (!done) print name "=" value }
	' .env > .env.new
	mv .env.new .env
}

token=$(sed -n 's/^SHAREWERK_AUTH_TOKEN=//p' .env | head -n 1)
if [ -z "$token" ]; then
	if command -v openssl > /dev/null 2>&1; then
		token=$(openssl rand -hex 32)
	else
		token=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
	fi
	set_var SHAREWERK_AUTH_TOKEN "$token"
fi
set_var SHAREWERK_AUTH_MODE token
set_var COMPOSE_FILE "$compose_file"
if [ "$mode" = domain ]; then
	set_var SHAREWERK_DOMAIN "$value"
else
	set_var TS_AUTHKEY "$value"
fi
umask 022
mkdir -p secrets

echo "Wrote .env ($compose_file)."
if [ "$start" = no ]; then
	echo "Start Sharewerk with: docker compose up -d"
	exit 0
fi

command -v docker > /dev/null 2>&1 && docker compose version > /dev/null 2>&1 ||
	fail "Docker with Compose is missing. Install it (https://docs.docker.com/engine/install/), then run ./setup.sh again."
docker compose pull
docker compose up -d

echo
if [ "$mode" = domain ]; then
	echo "Sharewerk starts at https://$value"
	echo "(the first start takes a minute: Caddy gets the certificate)."
else
	echo "Sharewerk starts in your tailnet at https://${TS_HOSTNAME:-sharewerk}.<your-tailnet>.ts.net"
	echo "(the exact name is in the Tailscale admin console, Machines)."
fi
echo "Open it on your phone and sign in with this access token (also in .env):"
echo
echo "  $token"
echo
echo "Next: install the app and add the cookies, see docs/getting-started.md."
