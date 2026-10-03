#!/usr/bin/env bash
# Install hid-gamesir via DKMS

set -e

PKG_NAME="hid-gamesir"
PKG_VER="0.1.0"
SRC_DIR="/usr/src/${PKG_NAME}-${PKG_VER}"

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (e.g. with sudo)."
    exit 1
fi

echo "[*] Registering ${PKG_NAME}-${PKG_VER} into DKMS..."
mkdir -p "${SRC_DIR}"
cp -r ../* "${SRC_DIR}/" 2>/dev/null || cp -r ./* "${SRC_DIR}/"

dkms add -m "${PKG_NAME}" -v "${PKG_VER}"
dkms build -m "${PKG_NAME}" -v "${PKG_VER}"
dkms install -m "${PKG_NAME}" -v "${PKG_VER}"

echo "[*] Installing udev rules..."
if [ -f "${SRC_DIR}/udev/99-hid-gamesir.rules" ]; then
    cp "${SRC_DIR}/udev/99-hid-gamesir.rules" /etc/udev/rules.d/
    udevadm control --reload-rules
    udevadm trigger
fi

echo "[+] Successfully installed ${PKG_NAME}-${PKG_VER} via DKMS!"
