# `hid-gamesir` - Linux Kernel HID Driver for GameSir Controllers

[![Build & Test](https://github.com/fchicout/hid-gamesir/actions/workflows/build-test.yml/badge.svg)](https://github.com/fchicout/hid-gamesir/actions/workflows/build-test.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=fchicout_hid-gamesir&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=fchicout_hid-gamesir)
[![License: GPL-2.0](https://img.shields.io/badge/License-GPL_2.0-blue.svg)](LICENSE)
[![SemVer](https://img.shields.io/badge/semver-0.1.0-blue)](https://semver.org)

An out-of-tree Linux Kernel module and DKMS package providing dedicated hardware handling, battery gauge fixes, and telemetry handling for **GameSir** / **Guangzhou Chicken Run Network Technology Co., Ltd.** controllers.

---

## 📌 Problem Background: The "5% Battery" Anomaly

Many GameSir multi-platform controllers (e.g., Nova, Nova Lite, T4 Pro, T4 Cyclone, G7) identify over USB using Sony's Vendor and Product IDs (`054c:09cc`, DualShock 4 CUH-ZCT2x) to ensure broad compatibility with games and game engines.

However:
1. Genuine DualShock 4 controllers transmit battery gauge telemetry (0–10 / 0–100%) in the lower nibble of byte offset 30 in report `0x01`.
2. GameSir firmware leaves this byte set to `0x00` in standard USB operation.
3. The upstream Linux kernel driver `hid-playstation` (`drivers/hid/hid-playstation.c`) calculates:
   $$\text{Capacity} = \min((\text{raw\_level} \times 10) + 5, 100)$$
   When $\text{raw\_level} = 0$, this formula permanently evaluates to **`5%`**.
4. The kernel `power_supply` subsystem and `UPower` continuously flag a false **"Critical Low Battery"** alarm on desktop environments (GNOME, KDE, Steam).

---

## 🎯 Solution Architecture

`hid-gamesir` sits as a specialized Linux HID driver:
- **Device Identification:** Matches `054c:09cc`, but inspects `hdev->name` and USB descriptors for `"Guangzhou Chicken Run"` or `"GameSir"`. Genuine Sony DualShock 4 controllers are yielded back to `hid-playstation`.
- **Battery Management:** Suppresses false low-battery nodes and isolates GameSir-specific telemetry.
- **DKMS Integration:** Automatically rebuilds on kernel updates.

---

## 🛠️ Installation & Usage

### Method 1: Automatic DKMS Installation (Recommended)

```bash
git clone https://github.com/fchicout/hid-gamesir.git
cd hid-gamesir
sudo ./scripts/dkms-install.sh
```

To uninstall:
```bash
sudo ./scripts/dkms-remove.sh
```

### Method 2: Manual Out-of-Tree Build

```bash
# Build module for currently running kernel
make

# Test load kernel module
sudo insmod hid-gamesir.ko

# Inspect module log
sudo dmesg | grep hid-gamesir

# Unload
sudo rmmod hid-gamesir
```

---

## 📊 SonarCloud Setup Guide

To connect this repository to **SonarCloud**:

1. Log into [SonarCloud.io](https://sonarcloud.io/) with your GitHub account (`fchicout`).
2. Click **"+"** (Top right) $\rightarrow$ **Analyze new project**.
3. Select the organization: **`fchicout`**.
4. Choose the repository: **`hid-gamesir`** and click **Set Up**.
5. Choose **With GitHub Actions** as the analysis method.
6. Copy the generated `SONAR_TOKEN`.
7. In your GitHub repository:
   - Go to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
   - Click **New repository secret**.
   - Name: `SONAR_TOKEN`.
   - Secret: *(paste your Sonar token)*.
8. The workflow in [`.github/workflows/sonarcloud.yml`](.github/workflows/sonarcloud.yml) will trigger on each push or pull request to `main`.

---

## 🌿 Development & Versioning

- **Semantic Versioning:** Follows [SemVer 2.0.0](https://semver.org/).
- **Conventional Commits:** All commits follow atomic `feat:`, `fix:`, `docs:`, `ci:`, `chore:`.
- **Kernel Style Guide:** Code formatted adhering to Linux kernel coding conventions via [`.clang-format`](.clang-format).

---

## 📜 License

Licensed under the **GNU General Public License v2.0 (GPL-2.0)** to match Linux Kernel upstream compatibility. See [LICENSE](LICENSE) for details.
