# -*- coding: utf-8 -*-
"""
Main emulator object for the fx-991CN X (ClassWiz) running on the HP Prime.

Ported from the C++ CasioEmuNeo Emulator.cpp + Emulator.hpp.  All the Lua,
debug, ROP and injection machinery has been removed.  The loop is frame driven:
run a batch of machine cycles, refresh the LCD through hpprime, then sample the
keyboard (also through hpprime).
"""

from . import model
from .chipset import Chipset
from .display import Display


class Emulator(object):
    def __init__(self):
        self.hardware_id = model.hardware_id
        self.strict_memory = False
        self.pause_on_mem_error = False

        self.chipset = Chipset(self)
        self.chipset.setup()
        self.chipset.setup_internals()
        self.chipset.reset()

        self.display = Display(self.chipset)

        # state for keyboard polling
        self._last_key = -1

    # ------------------------------------------------------------------
    def handle_memory_error(self):
        # default behaviour: ignore (do not pause)
        pass

    # ------------------------------------------------------------------
    def _handle_key(self, key):
        """Translate an HP Prime key code into a calculator key press.

        Called once per distinct key down / key up transition.
        """
        kb = self.chipset.peripherals[3]  # Keyboard peripheral
        name = model.prime_key_map.get(key)
        if name is None:
            return
        if name not in kb.buttons_by_name:
            return
        kb.press_button(kb.buttons_by_name[name], stick=False)

    def _handle_key_release(self):
        kb = self.chipset.peripherals[3]
        kb.release_all()

    # ------------------------------------------------------------------
    def run_once(self, ticks=None):
        """Run one frame: N machine cycles, paint, poll keyboard."""
        if ticks is None:
            ticks = model.ticks_per_frame
        chipset = self.chipset
        for _ in range(ticks):
            chipset.tick()
        # refresh display
        try:
            self.display.paint()
        except Exception as e:
            # never let a display hiccup kill the emulator on device
            print('display error:', e)

        # poll keyboard
        key = -1
        try:
            import hpprime
            key = hpprime.getkey()
        except ImportError:
            # local testing fallback: read a line from stdin
            key = self._local_getkey()
        if key != -1 and key != self._last_key:
            # key down
            self._handle_key(key)
            self._last_key = key
        elif key == -1 and self._last_key != -1:
            # key up
            self._handle_key_release()
            self._last_key = -1
        return key

    # ------------------------------------------------------------------
    def _local_getkey(self):
        # Only used when hpprime is unavailable (off-device smoke test).
        try:
            import sys
            line = sys.stdin.readline().strip()
        except Exception:
            return -1
        if not line:
            return -1
        try:
            return int(line)
        except ValueError:
            # accept single characters mapped via a tiny table
            m = {'0':48,'1':49,'2':50,'3':51,'4':52,'5':53,'6':54,'7':55,'8':56,'9':57,
                 '+':43,'-':45,'*':42,'/':47,'.':44,' ':32,'\x1b':0,'\r':13,'\x08':8}
            if line in m:
                return m[line]
            # arrow words
            aw = {'up':2,'down':3,'left':4,'right':5,'exe':1,'ac':0}
            if line.lower() in aw:
                return aw[line.lower()]
            return -1
