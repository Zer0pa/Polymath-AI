#!/usr/bin/env bash
# Termux SSH server setup for remote monitoring during fridge mode.
#
# After this script runs, the host can:
#   ssh -p 8022 -i ~/.ssh/polymath_termux <termux_user>@<phone_wifi_ip>
#
# Idempotent. Authorises the host's public key (passed in $1).

set -uo pipefail

HOST_PUBKEY="${1:-}"

if [[ -z "${HOST_PUBKEY}" ]]; then
    echo "usage: $0 '<host ssh public key, one line>'"
    echo "  on the host: cat ~/.ssh/polymath_termux.pub"
    exit 2
fi

# 1. Install OpenSSH (server is included).
pkg install -y openssh termux-api 2>&1 | tail -5

# 2. Set a passphrase-less default password so the very first connection
#    can land. (sshd accepts a default password for the Termux user.)
#    Once pubkey auth works, we disable password auth in step 5.
echo "[sshd-setup] make sure you set a password with 'passwd' if not already set"

# 3. Authorise the host's public key.
mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"
AUTH="${HOME}/.ssh/authorized_keys"
touch "${AUTH}"
chmod 600 "${AUTH}"
if grep -qF "${HOST_PUBKEY}" "${AUTH}" 2>/dev/null ; then
    echo "[sshd-setup] host pubkey already authorised"
else
    echo "${HOST_PUBKEY}" >> "${AUTH}"
    echo "[sshd-setup] host pubkey added"
fi

# 4. Tighten sshd_config: pubkey only, default port 8022 (Termux can't bind
#    privileged ports without root).
SSHD_CONF="${PREFIX}/etc/ssh/sshd_config"
if [[ -f "${SSHD_CONF}" ]]; then
    sed -i.bak \
        -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
        -e 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' \
        "${SSHD_CONF}"
fi

# 5. Start sshd.
sshd

# 6. Report.
PORT=8022
WIFI_IP="$(ifconfig 2>/dev/null | awk '/inet / && $2 !~ /^127/ {print $2; exit}')"
echo "[sshd-setup] sshd started"
echo "[sshd-setup] connect from host with:"
echo "    ssh -p ${PORT} -i ~/.ssh/polymath_termux $(whoami)@${WIFI_IP:-<phone-wifi-ip>}"
echo ""
echo "[sshd-setup] for fridge mode: pre-test the SSH path BEFORE closing the fridge door."
