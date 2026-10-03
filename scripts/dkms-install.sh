#!/usr/bin/env bash
# Install hid-gamesir via DKMS

set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

PKG_NAME="hid-gamesir"
PKG_VER="0.1.0"
SRC_DIR="/usr/src/${PKG_NAME}-${PKG_VER}"

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (e.g. with sudo): sudo ./scripts/dkms-install.sh"
    exit 1
fi

echo "[*] Cleaning any stale ${PKG_NAME}-${PKG_VER} from DKMS..."
dkms remove -m "${PKG_NAME}" -v "${PKG_VER}" --all 2>/dev/null || true
rm -rf "${SRC_DIR}"

echo "[*] Copying source tree from ${REPO_ROOT} to ${SRC_DIR}..."
mkdir -p "${SRC_DIR}"
cp "${REPO_ROOT}/Kbuild" "${REPO_ROOT}/Makefile" "${REPO_ROOT}/dkms.conf" "${SRC_DIR}/"
cp -r "${REPO_ROOT}/src" "${SRC_DIR}/"
if [ -d "${REPO_ROOT}/udev" ]; then
    cp -r "${REPO_ROOT}/udev" "${SRC_DIR}/"
fi

echo "[*] Registering, building, and installing via DKMS..."
dkms add -m "${PKG_NAME}" -v "${PKG_VER}"
dkms build -m "${PKG_NAME}" -v "${PKG_VER}"
dkms install -m "${PKG_NAME}" -v "${PKG_VER}"

echo "[*] Installing udev rules..."
if [ -f "${SRC_DIR}/udev/99-hid-gamesir.rules" ]; then
    cp "${SRC_DIR}/udev/99-hid-gamesir.rules" /etc/udev/rules.d/
    udevadm control --reload-rules
    udevadm trigger
fi

echo "[*] Loading module..."
modprobe "${PKG_NAME}" 2>/dev/null || true

echo "[+] Successfully installed ${PKG_NAME}-${PKG_VER} via DKMS!"
