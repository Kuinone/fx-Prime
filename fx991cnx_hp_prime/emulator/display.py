# -*- coding: utf-8 -*-
"""
Display layer for the fx-991CN X emulator on the HP Prime.

All screen output is done through the hpprime module (the Prime's MicroPython
graphics API).  No other graphics library is used.

A small fallback is provided (when hpprime cannot be imported) so the emulator
can be smoke-tested on a normal computer; the real calculator always uses
hpprime.
"""

try:
    import hpprime
    _have_hpprime = True
except ImportError:
    _have_hpprime = False

from . import model


# HP Prime screen size
_SCREEN_W = 320
_SCREEN_H = 240

# LCD dot-matrix geometry (fx-991CN X, CLASSWIZ)
_LCD_W = model.ROW_SIZE_DISP * 8          # 24 * 8 = 192
_LCD_H = model.N_ROW                       # 63

# Where to draw the LCD on the Prime screen
_LCD_X = (_SCREEN_W - _LCD_W) // 2         # 64
_LCD_Y = 26

_COL_ON = 0x000000   # pixel "on"  (black ink)
_COL_OFF = 0xC0C0C0  # pixel "off" (light grey)
_COL_BG = 0xFFFFFF   # background (white)
_COL_STATUS = 0x000000
_COL_BORDER = 0x000000


class Display(object):
    """Binds the emulator screen buffer to the HP Prime LCD."""

    def __init__(self, chipset):
        self.chipset = chipset
        screen = chipset.peripherals[2]  # Screen peripheral (index in list)
        self.buffer = screen.screen_buffer
        self.n_row = screen.n_row
        self.row_size = screen.row_size
        self.offset = screen.offset
        self.row_size_disp = screen.row_size_disp
        self._last = None   # previous rendered state, to avoid needless repaints

    # ------------------------------------------------------------------
    def _get_mode(self):
        return self.chipset.peripherals[2].screen_mode

    def _get_contrast(self):
        return self.chipset.peripherals[2].screen_contrast

    # ------------------------------------------------------------------
    def _changed(self):
        """Return True if the visible LCD has changed since the last paint."""
        buf = self.buffer
        rsc = self.row_size_disp
        rs = self.row_size
        key = bytearray(self.n_row * rsc)
        k = 0
        for iy in range(self.n_row):
            base = iy * rs + self.offset
            for ix in range(rsc):
                key[k] = buf[base + ix]
                k += 1
        key = bytes(key)
        mode = self._get_mode()
        if key == self._last and mode == self._last_mode:
            return False
        self._last = key
        self._last_mode = mode
        return True

    # ------------------------------------------------------------------
    def paint(self, force=False):
        """Redraw the calculator screen (LCD + status row) via hpprime."""
        buf = self.buffer
        mode = self._get_mode()
        contrast = self._get_contrast()

        if mode == 4:
            clear_dots = True
            status = False
        elif mode == 5:
            clear_dots = False
            status = True
        elif mode == 6:
            clear_dots = True
            status = True
        else:
            # unknown / off mode: just clear
            self._clear()
            return

        ink_alpha_on = 20 + contrast * 16
        if ink_alpha_on > 255:
            ink_alpha_on = 255
        ink_alpha_off = (contrast - 8) * 7
        if ink_alpha_off < 0:
            ink_alpha_off = 0

        if not _have_hpprime:
            self._paint_text(buf, mode, status, clear_dots)
            return

        # blank the whole screen
        self._clear()

        # status row
        if status:
            status_txt = []
            for (label, off, m) in model.status_indicators:
                if buf[off] & m:
                    status_txt.append(label)
            self._text(2, 4, ' '.join(status_txt))

        # dot matrix
        rs = self.row_size
        rsc = self.row_size_disp
        for iy in range(self.n_row):
            base = iy * rs + self.offset
            y = _LCD_Y + iy
            for ix in range(rsc):
                byte = buf[base + ix]
                if byte == 0:
                    continue
                x = _LCD_X + ix * 8
                mask = 0x80
                for b in range(8):
                    if byte & mask:
                        hpprime.set_pixel(x + b, y, _COL_ON)
                    else:
                        hpprime.set_pixel(x + b, y, _COL_OFF)
                    mask >>= 1

    # ------------------------------------------------------------------
    def _clear(self):
        if not _have_hpprime:
            return
        hpprime.fillrect(0, 0, _SCREEN_W - 1, _SCREEN_H - 1, _COL_BG)

    def _text(self, x, y, s):
        if not _have_hpprime:
            print(s)
            return
        try:
            hpprime.draw_string(x, y, s, _COL_STATUS, _COL_BG)
        except Exception:
            # older firmware may use draw_string without colours
            hpprime.draw_string(x, y, s)

    # text fallback used during local testing --------------------------
    def _paint_text(self, buf, mode, status, clear_dots):
        out = []
        if status:
            lbl = []
            for (label, off, m) in model.status_indicators:
                if buf[off] & m:
                    lbl.append(label)
            out.append('STATUS: ' + ' '.join(lbl))
        rs = self.row_size
        rsc = self.row_size_disp
        for iy in range(self.n_row):
            row = []
            base = iy * rs + self.offset
            for ix in range(rsc):
                byte = buf[base + ix]
                mask = 0x80
                for b in range(8):
                    row.append('#' if (byte & mask) else '.')
                    mask >>= 1
            out.append(''.join(row))
        print('--- screen ---')
        for line in out:
            print(line)
