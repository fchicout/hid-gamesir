#!/usr/bin/env bash
# Remove hid-gamesir from DKMS

set -e

PKG_NAME="hid-gamesir"
PKG_VER="0.1.0"
SRC_DIR="/usr/src/${PKG_NAME}-${PKG_VER}"

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (e.g. with sudo)."
    exit 1
fi

echo "[*] Removing ${PKG_NAME}-${PKG_VER} from DKMS..."
dkms remove -m "${PKG_NAME}" -v "${PKG_VER}" --all || true
rm -rf "${SRC_DIR}"
rm -f "/etc/udev/rules.d/99-hid-gamesir.rules"

udevadm control --reload-rules
udevadm trigger

echo "[+] Successfully removed ${PKG_NAME}-${PKG_VER} from DKMS!"
