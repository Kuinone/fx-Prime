# -*- coding: utf-8 -*-
"""
Entry point for the fx-991CN X emulator on the HP Prime.

Run this module on the calculator; it boots the firmware, renders the LCD on
the Prime screen and accepts keyboard input through hpprime.
"""

from .emu import Emulator


def main():
    emu = Emulator()
    # Initial paint
    emu.display.paint(force=True)
    # Main loop
    while True:
        emu.run_once()


# Local invocation:  python3 -m fx991cnx_hp_prime.emulator.main
if __name__ == '__main__':
    main()
