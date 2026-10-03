#!/usr/bin/env python3
"""
GameSir & Multi-Platform Controller Mode Detector
Identifies the active hardware mode:
  - PlayStation 4 (DS4) Mode (VID: 0x054c, PID: 0x09cc)
  - Xbox 360 / Xbox One (X-Input) Mode (VID: 0x045e, PID: 0x028e/0x02d1/0x0b12)
  - Nintendo Switch Pro Mode (VID: 0x057e, PID: 0x2009)
  - DirectInput / Android Mode (Generic HID)
"""

import os
import glob
from pathlib import Path

BOLD = "\033[1m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[1;36m"
MAGENTA = "\033[1;35m"
BLUE = "\033[1;34m"
GRAY = "\033[0;90m"
RESET = "\033[0m"

KNOWN_MODES = {
    ("054c", "09cc"): {
        "mode": "PlayStation 4 (DS4 Mode)",
        "protocol": "DualShock 4 HID",
        "expected_driver": "hid-gamesir / hid-playstation",
        "features": "Touchpad, Gyroscope/IMU, Lightbar, Stereo Audio",
        "hotkey_hint": "Hold 'Home + X' or 'Home + B' at plug-in to switch to Xbox mode"
    },
    ("054c", "05c4"): {
        "mode": "PlayStation 4 (DS4 v1 Mode)",
        "protocol": "DualShock 4 HID",
        "expected_driver": "hid-gamesir / hid-playstation",
        "features": "Touchpad, Gyroscope/IMU, Lightbar",
        "hotkey_hint": "Hold 'Home + X' or 'Home + B' at plug-in to switch to Xbox mode"
    },
    ("054c", "0ce6"): {
        "mode": "PlayStation 5 (DualSense Mode)",
        "protocol": "DualSense HID",
        "expected_driver": "hid-playstation",
        "features": "Touchpad, Adaptive Triggers, Haptic Rumble, Gyro",
        "hotkey_hint": ""
    },
    ("045e", "028e"): {
        "mode": "Xbox 360 (X-Input Mode)",
        "protocol": "X-Input (Direct USB / GIP)",
        "expected_driver": "xpad",
        "features": "Standard 14 buttons, Dual Analog Triggers, Dual Rumble Motors",
        "hotkey_hint": "Hold 'Home + A' or 'Home + B' to switch modes"
    },
    ("045e", "02d1"): {
        "mode": "Xbox One (X-Input Mode)",
        "protocol": "X-Input / GIP",
        "expected_driver": "xpad / xone",
        "features": "Impulse Triggers, Standard Xbox Layout",
        "hotkey_hint": "Hold 'Home + A' or 'Home + B' to switch modes"
    },
    ("045e", "0b12"): {
        "mode": "Xbox Series X|S (X-Input Mode)",
        "protocol": "X-Input / BLE GIP",
        "expected_driver": "xpad / xone",
        "features": "Share Button, Hybrid D-pad, Standard Xbox Layout",
        "hotkey_hint": ""
    },
    ("057e", "2009"): {
        "mode": "Nintendo Switch Pro Mode",
        "protocol": "Switch Pro Subcommand Protocol",
        "expected_driver": "hid-nintendo",
        "features": "Nintendo A/B X/Y layout, Motion Sensor, HD Rumble",
        "hotkey_hint": "Hold 'Home + X' while plugging in for PC/Xbox mode"
    },
}

def scan_controllers():
    print(f"{CYAN}========================================================================{RESET}")
    print(f"{BOLD} 🎮 Multi-Platform Gamepad Mode Detector{RESET}")
    print(f"{CYAN}========================================================================{RESET}\n")

    found_any = False

    # Scan USB devices in sysfs
    for dev_path in sorted(glob.glob("/sys/bus/usb/devices/*")):
        p = Path(dev_path)
        id_vendor_f = p / "idVendor"
        id_product_f = p / "idProduct"

        if not id_vendor_f.exists() or not id_product_f.exists():
            continue

        try:
            vid = id_vendor_f.read_text().strip().lower()
            pid = id_product_f.read_text().strip().lower()
            manufacturer = (p / "manufacturer").read_text().strip() if (p / "manufacturer").exists() else "Unknown"
            product = (p / "product").read_text().strip() if (p / "product").exists() else "Unknown"
            devnum = (p / "devnum").read_text().strip() if (p / "devnum").exists() else "?"
            busnum = (p / "busnum").read_text().strip() if (p / "busnum").exists() else "?"
        except Exception:
            continue

        key = (vid, pid)
        is_gamesir = "chicken run" in manufacturer.lower() or "gamesir" in manufacturer.lower() or "gamesir" in product.lower()

        if key in KNOWN_MODES or is_gamesir:
            found_any = True
            mode_info = KNOWN_MODES.get(key, {
                "mode": "Custom / DirectInput Mode",
                "protocol": "Generic HID",
                "expected_driver": "hid-generic",
                "features": "Standard Gamepad Buttons & Axes",
                "hotkey_hint": "Refer to GameSir user manual for mode shortcuts"
            })

            # Find active driver
            active_driver = "None"
            for child in p.glob("*:*"):
                driver_link = child / "driver"
                if driver_link.exists():
                    active_driver = driver_link.resolve().name
                    break

            # Also check HID drivers
            for hid_child in p.glob("*:*/*:*"):
                driver_link = hid_child / "driver"
                if driver_link.exists():
                    active_driver = driver_link.resolve().name

            tag = f"{GREEN}[GAMESIR CONTROLLER]{RESET}" if is_gamesir else f"{BLUE}[GAMEPAD]{RESET}"

            print(f"{tag} {BOLD}{product}{RESET} {GRAY}(Bus {busnum}, Dev {devnum}){RESET}")
            print(f"  {BOLD}Active Mode:{RESET}      {YELLOW}{mode_info['mode']}{RESET}")
            print(f"  {BOLD}Hardware VID:PID:{RESET} 0x{vid}:0x{pid} (Manufacturer: {manufacturer})")
            print(f"  {BOLD}Protocol:{RESET}         {mode_info['protocol']}")
            print(f"  {BOLD}Bound Driver:{RESET}     {CYAN}{active_driver}{RESET} (Expected: {mode_info['expected_driver']})")
            print(f"  {BOLD}Capabilities:{RESET}     {mode_info['features']}")

            if mode_info.get("hotkey_hint"):
                print(f"  {BOLD}Mode Switch Tip:{RESET}  {GRAY}{mode_info['hotkey_hint']}{RESET}")
            print("-" * 72)

    if not found_any:
        print(f"{YELLOW}No recognized gamepad (PS4/Xbox/Switch) found on the USB bus.{RESET}")
        print("Ensure the controller is turned on and connected via USB cable or wireless dongle.\n")

if __name__ == "__main__":
    scan_controllers()
