#!/usr/bin/env python3
"""
Real-Time Visual Gamepad Input & Paddle Tester (Linux)
Reads live events from Linux evdev (/dev/input/event*) or jsdev (/dev/input/js*)
Displays a full ASCII gamepad layout with real-time button highlights,
stick coordinates, analog triggers, and L4/R4 back paddle detection.
"""

import sys
import os
import glob
import struct
import select
import time
from pathlib import Path

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

# Linux Input Event Types & Codes
EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03

# Linux JS Event format
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

def find_gamepad_device():
    # Prefer /dev/input/js* or /dev/input/by-id/*
    by_id = sorted(glob.glob("/dev/input/by-id/*joystick*") + glob.glob("/dev/input/by-id/*event-joystick*"))
    if by_id:
        for p in by_id:
            if os.access(p, os.R_OK):
                return p
                
    js_devs = sorted(glob.glob("/dev/input/js*"))
    for p in js_devs:
        if os.access(p, os.R_OK):
            return p
            
    event_devs = sorted(glob.glob("/dev/input/event*"))
    for p in event_devs:
        if os.access(p, os.R_OK):
            return p
            
    return None

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
        # Axes (normalized -1.0 to 1.0 or 0.0 to 1.0)
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

def draw_hud(state: GamepadState, dev_path: str):
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
    lines.append(f" {BLUE}Device Node:{RESET} {dev_path}")
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
    lines.append(f"  {GRAY}[Press Ctrl+C to exit. Press buttons & sticks to see live updates]{RESET}")
    lines.append(f"{CYAN}------------------------------------------------------------------------{RESET}")

    sys.stdout.write(CLEAR_SCREEN + "\n".join(lines) + "\n")
    sys.stdout.flush()

def run_jsdev_tester(dev_path: str):
    fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    state = GamepadState()
    
    # JS event format: (uint32 time, int16 value, uint8 type, uint8 number)
    EVENT_FORMAT = "IhBB"
    EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

    sys.stdout.write(HIDE_CURSOR)
    draw_hud(state, dev_path)

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
                            # Standard Linux jsdev button indices
                            btn_names = {
                                0: "A", 1: "B", 2: "X", 3: "Y",
                                4: "L1", 5: "R1", 6: "L2", 7: "R2",
                                8: "SELECT", 9: "START", 10: "MODE",
                                11: "L3", 12: "R3", 13: "L4", 14: "R4"
                            }
                            b_name = btn_names.get(number, f"BTN_{number}")
                            if b_name in state.buttons:
                                state.buttons[b_name] = pressed
                            state.last_event_str = f"Button {b_name} {'PRESSED' if pressed else 'RELEASED'} (index {number})"
                            
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
                        
                draw_hud(state, dev_path)
    finally:
        os.close(fd)
        sys.stdout.write(SHOW_CURSOR)
        print("\nExited input tester.")

def main():
    target = None
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = find_gamepad_device()

    if not target:
        print(f"{RED}Error: No readable gamepad device found (/dev/input/js* or /dev/input/event*).{RESET}")
        print("Ensure the controller is connected or run with sudo.")
        sys.exit(1)

    print(f"{GREEN}Connecting to gamepad device:{RESET} {target}")
    run_jsdev_tester(target)

if __name__ == "__main__":
    main()
