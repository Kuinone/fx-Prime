# -*- coding: utf-8 -*-
"""
Model configuration for the Casio fx-991CN X (ClassWiz, hardware_id = 4).

This module replaces the original C++ emulator's "model.lua" configuration file.
It contains only the data the basic calculator emulator needs (no debug / ROP /
injection options).  Values that are hardware specific (button scan matrix,
sprite / on-screen pixel layout) are kept in this file so they can be tuned
without touching the emulation core.

External resource referenced here: "rom.bin" (the factory firmware image),
located next to this file / in the project directory.
"""

# Hardware model of the machine.  See Data/HardwareId.hpp:
#   HW_ES_PLUS   = 3
#   HW_CLASSWIZ  = 4   <-- fx-991CN X
#   HW_CLASSWIZ_II = 5
hardware_id = 4

# When False the emulator uses the same keyboard interface the official Casio
# emulator exposes (single-key reporting + ready/ko/ki shadow registers).
# When True it emulates the real hardware keyboard matrix with ghosting.
real_hardware = False

# Path to the firmware image, relative to this config file.
rom_path = "rom.bin"

# Value reported at the keyboard "pd" register (0xF050) on the emulator model.
pd_value = 0

# CSR mask: on the large memory model the code segment register is 4 bits.
csr_mask = 0x000F

# Cycles per second the machine is supposed to run at (used only to drive the
# timer peripheral).  fx-991CN X (CLASSWIZ) = 2 * 1024 * 1024.
cycles_per_second = 2048 * 1024

# Display dimensions of the LCD dot matrix (see Screen.cpp, HW_CLASSWIZ).
# N_ROW rows, each ROW_SIZE bytes, ROW_SIZE_DISP bytes are actually displayed.
N_ROW         = 63
ROW_SIZE      = 32
OFFSET        = 32
ROW_SIZE_DISP = 24

# LCD pixel buffer base address (Screen.cpp region_buffer).
screen_base = 0xF800
# Pixel buffer byte count = (N_ROW + 1) * ROW_SIZE
screen_size = (N_ROW + 1) * ROW_SIZE

# How many machine ticks to execute per rendered frame.  HP Prime is far slower
# than a desktop CPU, so we do not try to keep real-time speed; this value is a
# reasonable compromise between emulator responsiveness and screen refresh rate.
ticks_per_frame = 8000

# ---------------------------------------------------------------------------
# Keyboard layout.
#
# Every entry is:  (x, y, w, h, code, name)
#   x, y, w, h : on-screen rectangle of the key (only used for mouse/keyboard
#                driven layout; not required on the HP Prime but kept for
#                reference).
#   code       : scan code of the key.  High nibble = KO line, low nibble = KI
#                line.  0xFF means the POWER key.
#   name       : readable name.
#
# The fx-991CN X keyboard matrix is not shipped with this project, so this map
# is a best-effort starting point.  If a key does not respond on your machine,
# adjust the "code" values here to match your calculator's actual scan matrix.
# ---------------------------------------------------------------------------
button_map = [
    # Power (0xFF)
    (  0,   0, 40, 14, 0xFF, "POWER"),
    # Main function rows (scan matrix layout: KO 0..9 x KI 0..7)
    (  0,  14, 30, 14, 0x10, "MENU"),   # MENU / SETTINGS
    ( 31,  14, 30, 14, 0x11, "ALPHA"),
    ( 62,  14, 30, 14, 0x12, "X^2"),    # x^2
    ( 93,  14, 30, 14, 0x13, "LN"),     # ln
    (124,  14, 30, 14, 0x14, "LOG"),    # log
    (155,  14, 30, 14, 0x15, "RCL"),    # (reserved)
    (186,  14, 30, 14, 0x16, "x"),      # variable x
    (  0,  28, 30, 14, 0x20, "SHIFT"),
    ( 31,  28, 30, 14, 0x21, "OPTN"),
    ( 62,  28, 30, 14, 0x22, "UP"),     # replay up
    ( 93,  28, 30, 14, 0x23, "DOWN"),   # replay down
    (124,  28, 30, 14, 0x24, "LEFT"),   # replay left
    (155,  28, 30, 14, 0x25, "RIGHT"),  # replay right
    (186,  28, 30, 14, 0x26, "EXE"),    # EXE
    (  0,  42, 40, 14, 0x30, "DEL"),    # DEL
    ( 41,  42, 40, 14, 0x31, "AC_ON"),  # AC / ON
    ( 82,  42, 36, 14, 0x32, "DIV"),    # /
    (119,  42, 36, 14, 0x33, "MUL"),    # *
    (156,  42, 36, 14, 0x34, "SUB"),    # -
    (  0,  56, 36, 14, 0x40, "7"),
    ( 37,  56, 36, 14, 0x41, "8"),
    ( 74,  56, 36, 14, 0x42, "9"),
    (111,  56, 36, 14, 0x43, "DEL"),    # (reserved)
    (  0,  70, 36, 14, 0x50, "4"),
    ( 37,  70, 36, 14, 0x51, "5"),
    ( 74,  70, 36, 14, 0x52, "6"),
    (111,  70, 36, 14, 0x53, "ADD"),    # +
    (  0,  84, 36, 14, 0x60, "1"),
    ( 37,  84, 36, 14, 0x61, "2"),
    ( 74,  84, 36, 14, 0x62, "3"),
    (  0,  98, 36, 14, 0x70, "0"),
    ( 37,  98, 36, 14, 0x71, "DOT"),    # .
    ( 74,  98, 74, 14, 0x72, "NEG"),    # (-)
]

# ---------------------------------------------------------------------------
# Status-row indicators.  Each indicator is (label, buffer_offset, mask).
# The status bytes live in the first OFFSET bytes of the pixel buffer (row 0).
# See Screen.cpp sprite_bitmap for the CLASSWIZ model.
# ---------------------------------------------------------------------------
status_indicators = [
    ("S",     0x00, 0x01),
    ("A",     0x01, 0x01),
    ("M",     0x02, 0x01),
    ("STO",   0x03, 0x01),
    ("MATH",  0x05, 0x01),
    ("D",     0x06, 0x01),
    ("R",     0x07, 0x01),
    ("G",     0x08, 0x01),
    ("FIX",   0x09, 0x01),
    ("SCI",   0x0A, 0x01),
    ("E",     0x0B, 0x01),
    ("CMPLX", 0x0C, 0x01),
    ("ANGLE", 0x0D, 0x01),
    ("^",     0x0F, 0x01),
    ("<-",    0x10, 0x01),
    ("v",     0x11, 0x01),
    ("^",     0x12, 0x01),
    ("->",    0x13, 0x01),
    ("PAUSE", 0x15, 0x01),
    ("SUN",   0x16, 0x01),
]

# Ink colour used to tint the pixels (R, G, B).  fx-991CN X uses dark ink.
ink_colour = (0, 0, 0)

# ---------------------------------------------------------------------------
# HP Prime key code -> calculator key name.
# hpprime.getkey() returns the code of the key that is currently held, or -1
# when no key is held.  The codes below are the standard HP Prime codes:
#   0 = Escape, 1 = Enter, 2 = Up, 3 = Down, 4 = Left, 5 = Right,
#   digits 48-57 are '0'..'9', 42='*', 43='+', 45='-', 47='/', 44=',' .
# ---------------------------------------------------------------------------
prime_key_map = {
    0:  "AC_ON",
    1:  "EXE",
    2:  "UP",
    3:  "DOWN",
    4:  "LEFT",
    5:  "RIGHT",
    48: "0", 49: "1", 50: "2", 51: "3", 52: "4",
    53: "5", 54: "6", 55: "7", 56: "8", 57: "9",
    42: "MUL", 43: "ADD", 45: "SUB", 47: "DIV", 44: "DOT",
    8:  "DEL", 13: "EXE", 32: "EXE",
}
