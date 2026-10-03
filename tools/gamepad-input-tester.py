#!/usr/bin/env python3
"""
Real-Time Visual Gamepad Input & Paddle Tester (Linux)
Supports both Linux evdev (/dev/input/event*) and jsdev (/dev/input/js*) APIs.
Displays a live ASCII gamepad layout with real-time button highlights,
stick coordinates, analog triggers, and L4/R4 back paddle detection.
"""

import sys
import os
import glob
import struct
import select
import time
import argparse
import fcntl
import array
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# ANSI Escape Colors
BOLD = "\033[1m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[1;36m"
RED = "\033[1;31m"
BLUE = "\033[1;34m"
MAGENTA = "\033[1;35m"
GRAY = "\033[0;90m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

# Linux Input Event Types
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

# Linux Input Event Button Codes (Standard Gamepad)
BTN_SOUTH = 0x130          # 304 (A / Cross)
BTN_EAST = 0x131           # 305 (B / Circle)
BTN_C = 0x132              # 306
BTN_NORTH = 0x133          # 307 (X / Triangle)
BTN_WEST = 0x134           # 308 (Y / Square)
BTN_Z = 0x135              # 309
BTN_TL = 0x136             # 310 (L1 / LB)
BTN_TR = 0x137             # 311 (R1 / RB)
BTN_TL2 = 0x138            # 312 (L2 / LT button)
BTN_TR2 = 0x139            # 313 (R2 / RT button)
BTN_SELECT = 0x13a         # 314 (Back / Select / Share)
BTN_START = 0x13b          # 315 (Start / Options)
BTN_MODE = 0x13c           # 316 (Home / Guide / PS / M)
BTN_THUMBL = 0x13d         # 317 (L3)
BTN_THUMBR = 0x13e         # 318 (R3)
BTN_TRIGGER_HAPPY1 = 0x2c0 # 704 (L4 / M1 Paddle)
BTN_TRIGGER_HAPPY2 = 0x2c1 # 705 (R4 / M2 Paddle)

# Linux Absolute Axes
ABS_X = 0x00               # Left Stick X
ABS_Y = 0x01               # Left Stick Y
ABS_Z = 0x02               # Left Trigger (or Right Stick X)
ABS_RX = 0x03              # Right Stick X
ABS_RY = 0x04              # Right Stick Y
ABS_RZ = 0x05              # Right Trigger (or Right Stick Y)
ABS_HAT0X = 0x10           # D-Pad X (-1, 0, 1)
ABS_HAT0Y = 0x11           # D-Pad Y (-1, 0, 1)

# Linux JS Event format (legacy /dev/input/js*)
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

def get_device_name(dev_path: str) -> str:
    """Query human-readable device name via evdev ioctl or sysfs."""
    try:
        if "event" in dev_path:
            fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
            buf = array.array('B', [0] * 256)
            # EVIOCGNAME(256)
            fcntl.ioctl(fd, 0x80ff4506, buf, True)
            os.close(fd)
            name = buf.tobytes().split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
            if name:
                return name
    except Exception:
        pass

    # Sysfs fallback
    node_name = os.path.basename(os.path.realpath(dev_path))
    name_file = Path(f"/sys/class/input/{node_name}/device/name")
    if name_file.exists():
        try:
            return name_file.read_text().strip()
        except Exception:
            pass

    return os.path.basename(dev_path)

def list_devices() -> List[Dict[str, Any]]:
    """Enumerate all available gamepad device nodes."""
    devices = []
    seen_realpaths = set()

    # 1. Scan /dev/input/by-id/
    for p in sorted(glob.glob("/dev/input/by-id/*joystick*") + glob.glob("/dev/input/by-id/*event-joystick*")):
        real = os.path.realpath(p)
        if real in seen_realpaths:
            continue
        seen_realpaths.add(real)
        readable = os.access(p, os.R_OK)
        dev_type = "evdev" if "event" in real else "jsdev"
        name = get_device_name(p)
        devices.append({
            "path": p,
            "realpath": real,
            "type": dev_type,
            "name": name,
            "readable": readable
        })

    # 2. Scan /dev/input/js*
    for p in sorted(glob.glob("/dev/input/js*")):
        real = os.path.realpath(p)
        if real in seen_realpaths:
            continue
        seen_realpaths.add(real)
        readable = os.access(p, os.R_OK)
        name = get_device_name(p)
        devices.append({
            "path": p,
            "realpath": real,
            "type": "jsdev",
            "name": name,
            "readable": readable
        })

    # 3. Scan /dev/input/event*
    for p in sorted(glob.glob("/dev/input/event*")):
        real = os.path.realpath(p)
        if real in seen_realpaths:
            continue
        seen_realpaths.add(real)
        name = get_device_name(p)
        # Filter obvious keyboard/mouse/power buttons
        if any(term in name.lower() for term in ["gamepad", "controller", "joystick", "chicken run", "sony", "xbox", "gamesir"]):
            readable = os.access(p, os.R_OK)
            devices.append({
                "path": p,
                "realpath": real,
                "type": "evdev",
                "name": name,
                "readable": readable
            })

    return devices

def select_best_device() -> Optional[Dict[str, Any]]:
    devs = list_devices()
    if not devs:
        return None

    # Prefer readable devices with controller/gamesir in name
    preferred = [d for d in devs if d["readable"] and any(k in d["name"].lower() for k in ["chicken run", "gamesir", "controller", "dualshock", "gamepad"])]
    if preferred:
        # Prefer evdev for direct paddle (L4/R4) event codes
        ev_first = sorted(preferred, key=lambda d: 0 if d["type"] == "evdev" else 1)
        return ev_first[0]

    # Fallback to any readable device
    readable = [d for d in devs if d["readable"]]
    if readable:
        return readable[0]

    return devs[0]

class GamepadState:
    def __init__(self):
        # Buttons
        self.buttons = {
            "A": False, "B": False, "X": False, "Y": False,
            "L1": False, "R1": False, "L2": False, "R2": False,
            "SELECT": False, "START": False, "MODE": False,
            "L3": False, "R3": False,
            "L4": False, "R4": False,
        }
        # Axes
        self.left_x = 0.0
        self.left_y = 0.0
        self.right_x = 0.0
        self.right_y = 0.0
        self.trigger_l = 0.0
        self.trigger_r = 0.0
        self.dpad_x = 0
        self.dpad_y = 0
        self.last_event_str = "None"
        self.event_count = 0

def draw_hud(state: GamepadState, dev_info: Dict[str, Any]):
    def btn_tag(name: str, pressed: bool) -> str:
        if pressed:
            return f"\033[1;30;42m {name} \033[0m"
        else:
            return f"{GRAY}[{name}]{RESET}"

    # Visual Sticks
    lx = int(round((state.left_x + 1.0) * 5))
    ly = int(round((state.left_y + 1.0) * 2))
    rx = int(round((state.right_x + 1.0) * 5))
    ry = int(round((state.right_y + 1.0) * 2))

    # Trigger bars
    l2_bar = "█" * int(round(state.trigger_l * 8))
    r2_bar = "█" * int(round(state.trigger_r * 8))

    dpad_up = state.dpad_y < 0
    dpad_down = state.dpad_y > 0
    dpad_left = state.dpad_x < 0
    dpad_right = state.dpad_x > 0

    lines = []
    lines.append(f"{CYAN}========================================================================{RESET}")
    lines.append(f"{BOLD} 🎮 GameSir Cyclone 2 Live Input & Paddle Tester{RESET}  {GRAY}(Events: {state.event_count}){RESET}")
    lines.append(f" {BLUE}Device:{RESET} {BOLD}{dev_info.get('name', 'Unknown')}{RESET}")
    lines.append(f" {BLUE}Node:{RESET}   {dev_info.get('path')} {GRAY}(Real: {dev_info.get('realpath')}, Backend: {dev_info.get('type').upper()}){RESET}")
    lines.append(f"{CYAN}========================================================================{RESET}")
    lines.append("")
    lines.append(f"     LT: {btn_tag('L2', state.buttons['L2'])} {CYAN}[{l2_bar:<8}]{RESET}                  RT: {btn_tag('R2', state.buttons['R2'])} {CYAN}[{r2_bar:<8}]{RESET}")
    lines.append(f"     LB: {btn_tag('L1', state.buttons['L1'])}                                   RB: {btn_tag('R1', state.buttons['R1'])}")
    lines.append("     ┌────────────────────────────────────────────────────────┐")
    lines.append(f"     │  D-PAD             SELECT      HOME     START            │")
    lines.append(f"     │    {btn_tag('▲', dpad_up)}              {btn_tag('BACK', state.buttons['SELECT'])}     {btn_tag('PS/M', state.buttons['MODE'])}    {btn_tag('START', state.buttons['START'])}            │")
    lines.append(f"     │  {btn_tag('◀', dpad_left)}   {btn_tag('▶', dpad_right)}                                         {btn_tag('Y', state.buttons['Y'])}       │")
    lines.append(f"     │    {btn_tag('▼', dpad_down)}         LEFT STICK          RIGHT STICK     {btn_tag('X', state.buttons['X'])}     {btn_tag('B', state.buttons['B'])}   │")
    lines.append(f"     │                 (X:{state.left_x:+0.2f}, Y:{state.left_y:+0.2f})    (X:{state.right_x:+0.2f}, Y:{state.right_y:+0.2f})       {btn_tag('A', state.buttons['A'])}       │")
    lines.append(f"     │                    {btn_tag('L3', state.buttons['L3'])}                 {btn_tag('R3', state.buttons['R3'])}                 │")
    lines.append("     │                                                        │")
    lines.append(f"     │    [REAR PADDLE L4]                [REAR PADDLE R4]    │")
    lines.append(f"     │         {btn_tag('L4 / M1', state.buttons['L4'])}                         {btn_tag('R4 / M2', state.buttons['R4'])}         │")
    lines.append("     └────────────────────────────────────────────────────────┘")
    lines.append("")
    lines.append(f"  {BOLD}Last Event:{RESET} {YELLOW}{state.last_event_str}{RESET}")
    lines.append(f"  {GRAY}[Press Ctrl+C to exit. Press buttons, paddles & sticks to see live updates]{RESET}")
    lines.append(f"{CYAN}------------------------------------------------------------------------{RESET}")

    sys.stdout.write(CLEAR_SCREEN + "\n".join(lines) + "\n")
    sys.stdout.flush()

def run_evdev_tester(dev_info: Dict[str, Any]):
    """Process live Linux evdev (struct input_event) packets."""
    dev_path = dev_info["realpath"]
    fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    state = GamepadState()

    # struct input_event: (timeval time [16B on 64bit], uint16 type, uint16 code, int32 value) = 24 bytes
    EVENT_FORMAT = "qqHHi"
    EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

    # Key code map
    KEY_MAP = {
        BTN_SOUTH: "A",
        BTN_EAST: "B",
        BTN_NORTH: "X",
        BTN_WEST: "Y",
        BTN_TL: "L1",
        BTN_TR: "R1",
        BTN_TL2: "L2",
        BTN_TR2: "R2",
        BTN_SELECT: "SELECT",
        BTN_START: "START",
        BTN_MODE: "MODE",
        BTN_THUMBL: "L3",
        BTN_THUMBR: "R3",
        BTN_TRIGGER_HAPPY1: "L4",
        BTN_TRIGGER_HAPPY2: "R4",
    }

    sys.stdout.write(HIDE_CURSOR)
    draw_hud(state, dev_info)

    try:
        while True:
            r, _, _ = select.select([fd], [], [], 0.05)
            if fd in r:
                while True:
                    try:
                        data = os.read(fd, EVENT_SIZE)
                        if len(data) < EVENT_SIZE:
                            break
                        _, _, ev_type, code, value = struct.unpack(EVENT_FORMAT, data)
                        state.event_count += 1

                        if ev_type == EV_KEY:
                            pressed = (value == 1)
                            b_name = KEY_MAP.get(code, f"KEY_0x{code:03x}")
                            if b_name in state.buttons:
                                state.buttons[b_name] = pressed
                            state.last_event_str = f"Button {b_name} {'PRESSED' if pressed else 'RELEASED'} (evdev code 0x{code:x}/{code})"

                        elif ev_type == EV_ABS:
                            # Standard 0-255 or -32768..32767
                            if code == ABS_X:
                                state.left_x = (value - 128) / 128.0 if value <= 255 else value / 32767.0
                            elif code == ABS_Y:
                                state.left_y = (value - 128) / 128.0 if value <= 255 else value / 32767.0
                            elif code == ABS_RX or code == ABS_Z:
                                if code == ABS_RX:
                                    state.right_x = (value - 128) / 128.0 if value <= 255 else value / 32767.0
                                else:
                                    state.trigger_l = value / 255.0 if value <= 255 else max(0.0, (value + 32768) / 65535.0)
                            elif code == ABS_RY or code == ABS_RZ:
                                if code == ABS_RY:
                                    state.right_y = (value - 128) / 128.0 if value <= 255 else value / 32767.0
                                else:
                                    state.trigger_r = value / 255.0 if value <= 255 else max(0.0, (value + 32768) / 65535.0)
                            elif code == ABS_HAT0X:
                                state.dpad_x = value
                            elif code == ABS_HAT0Y:
                                state.dpad_y = value

                            state.last_event_str = f"Axis 0x{code:x} = {value}"

                    except BlockingIOError:
                        break
                    except Exception:
                        break

                draw_hud(state, dev_info)
    finally:
        os.close(fd)
        sys.stdout.write(SHOW_CURSOR)
        print("\nExited input tester.")

def run_jsdev_tester(dev_info: Dict[str, Any]):
    """Process legacy Linux jsdev (struct js_event) packets."""
    dev_path = dev_info["realpath"]
    fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    state = GamepadState()

    # JS event format: (uint32 time, int16 value, uint8 type, uint8 number) = 8 bytes
    EVENT_FORMAT = "IhBB"
    EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

    sys.stdout.write(HIDE_CURSOR)
    draw_hud(state, dev_info)

    try:
        while True:
            r, _, _ = select.select([fd], [], [], 0.05)
            if fd in r:
                while True:
                    try:
                        data = os.read(fd, EVENT_SIZE)
                        if len(data) < EVENT_SIZE:
                            break
                        _, value, ev_type, number = struct.unpack(EVENT_FORMAT, data)
                        state.event_count += 1

                        # Strip init flag
                        ev_type = ev_type & ~JS_EVENT_INIT

                        if ev_type == JS_EVENT_BUTTON:
                            pressed = (value == 1)
                            btn_names = {
                                0: "A", 1: "B", 2: "X", 3: "Y",
                                4: "L1", 5: "R1", 6: "L2", 7: "R2",
                                8: "SELECT", 9: "START", 10: "MODE",
                                11: "L3", 12: "R3", 13: "L4", 14: "R4"
                            }
                            b_name = btn_names.get(number, f"BTN_{number}")
                            if b_name in state.buttons:
                                state.buttons[b_name] = pressed
                            state.last_event_str = f"Button {b_name} {'PRESSED' if pressed else 'RELEASED'} (jsdev index {number})"

                        elif ev_type == JS_EVENT_AXIS:
                            norm_val = value / 32767.0
                            if number == 0:
                                state.left_x = norm_val
                            elif number == 1:
                                state.left_y = norm_val
                            elif number == 2:
                                state.trigger_l = max(0.0, (norm_val + 1.0) / 2.0)
                            elif number == 3:
                                state.right_x = norm_val
                            elif number == 4:
                                state.right_y = norm_val
                            elif number == 5:
                                state.trigger_r = max(0.0, (norm_val + 1.0) / 2.0)
                            elif number == 6:
                                state.dpad_x = 1 if norm_val > 0.5 else (-1 if norm_val < -0.5 else 0)
                            elif number == 7:
                                state.dpad_y = 1 if norm_val > 0.5 else (-1 if norm_val < -0.5 else 0)
                            state.last_event_str = f"Axis {number} = {norm_val:+0.2f}"

                    except BlockingIOError:
                        break
                    except Exception:
                        break

                draw_hud(state, dev_info)
    finally:
        os.close(fd)
        sys.stdout.write(SHOW_CURSOR)
        print("\nExited input tester.")

def main():
    parser = argparse.ArgumentParser(description="Real-Time Visual Gamepad Input & Paddle Tester")
    parser.add_argument("-d", "--device", help="Path to /dev/input/event* or /dev/input/js* device node", default=None)
    parser.add_argument("-l", "--list", action="store_true", help="List all detected gamepad/joystick devices")
    parser.add_argument("--jsdev", action="store_true", help="Force jsdev (/dev/input/js*) backend mode")
    parser.add_argument("--evdev", action="store_true", help="Force evdev (/dev/input/event*) backend mode")
    args = parser.parse_args()

    if args.list:
        devs = list_devices()
        print(f"\n{BOLD}Detected Input Devices ({len(devs)}):{RESET}")
        print("------------------------------------------------------------------------")
        for idx, d in enumerate(devs, 1):
            access_str = f"{GREEN}Readable{RESET}" if d["readable"] else f"{RED}Permission Denied (run with sudo){RESET}"
            print(f" {idx}. {BOLD}{d['name']}{RESET}")
            print(f"    Path:    {d['path']} -> {d['realpath']}")
            print(f"    Type:    {d['type'].upper()}  |  Access: {access_str}")
        print("------------------------------------------------------------------------\n")
        return

    dev_info = None
    if args.device:
        target = args.device
        real = os.path.realpath(target)
        dev_type = "evdev" if "event" in real else "jsdev"
        if args.jsdev:
            dev_type = "jsdev"
        elif args.evdev:
            dev_type = "evdev"
        dev_info = {
            "path": target,
            "realpath": real,
            "type": dev_type,
            "name": get_device_name(target),
            "readable": os.access(target, os.R_OK)
        }
    else:
        dev_info = select_best_device()

    if not dev_info:
        print(f"{RED}Error: No gamepad/joystick device found under /dev/input/.{RESET}")
        print("Ensure the controller is connected via USB or run `sudo python3 tools/gamepad-input-tester.py --list`.")
        sys.exit(1)

    if not dev_info["readable"]:
        print(f"{RED}Error: Permission denied accessing {dev_info['path']}.{RESET}")
        print(f"Please run with sudo or check udev permissions:")
        print(f"  sudo python3 tools/gamepad-input-tester.py -d {dev_info['path']}")
        sys.exit(1)

    if dev_info["type"] == "evdev":
        run_evdev_tester(dev_info)
    else:
        run_jsdev_tester(dev_info)

if __name__ == "__main__":
    main()
