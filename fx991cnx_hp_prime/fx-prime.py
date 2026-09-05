# -*- coding: utf-8 -*-
"""
fx-991CN X (ClassWiz) emulator for the HP Prime.

Single-file MicroPython build.  The modules that originally made up the
`emulator` package (model, mmu, cpu, peripherals, chipset, display, emu,
main) have been merged into this one file so it can be copied to the
calculator and run directly, e.g.

    run("fx-prime.py")

The relative imports and module aliases of the package layout have been
removed; every name is now a plain global in this single namespace.

The firmware image `rom.bin` must sit next to this file (see
chipset.setup_internals).

Entry point: Emulator plus the main loop in main().
"""

############################################################################
# MODEL  (model.py)
############################################################################
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
############################################################################
# MMU  (mmu.py)
############################################################################
# -*- coding: utf-8 -*-
"""
Memory Management Unit.

Ported from the C++ emulator (Chipset/MMU.cpp + Chipset/MMURegion.hpp).
Kept as simple and fast as MicroPython allows.

Instead of the C++ per-byte function-pointer dispatch table we keep, for each
64 KiB segment, a small list of registered regions and scan them linearly.
Segments have few regions each, so this is cheap, and it avoids a huge table.
"""


class Region(object):
    """A contiguous block of address space backed by a read/write callback."""

    def __init__(self, base, size, read_fn, write_fn, userdata=None):
        self.base = base
        self.size = size
        self.end = base + size
        self.read_fn = read_fn
        self.write_fn = write_fn
        self.userdata = userdata

    def read(self, offset):
        return self.read_fn(self, offset)

    def write(self, offset, data):
        return self.write_fn(self, offset, data)


class MMU(object):
    def __init__(self, chipset):
        self.chipset = chipset
        self.rom_data = chipset.rom_data
        # segment index (address >> 16) -> list of Region
        self.segments = {}
        self.mem_error_paused = False

    # ------------------------------------------------------------------
    # region registration
    # ------------------------------------------------------------------
    def register_region(self, region):
        seg = region.base >> 16
        lst = self.segments.get(seg)
        if lst is None:
            lst = []
            self.segments[seg] = lst
        lst.append(region)

    def unregister_region(self, region):
        seg = region.base >> 16
        lst = self.segments.get(seg)
        if lst:
            try:
                lst.remove(region)
            except ValueError:
                pass

    def _lookup(self, offset):
        """Return the Region covering offset, or None."""
        lst = self.segments.get(offset >> 16)
        if not lst:
            return None
        for r in lst:
            if r.base <= offset < r.end:
                return r
        return None

    # ------------------------------------------------------------------
    # memory access
    # ------------------------------------------------------------------
    def read_code(self, offset):
        # offset must be a 20-bit, even address
        if offset & 1:
            self.chipset.emulator.handle_memory_error()
            return 0
        seg = offset >> 16
        off = offset & 0xFFFF
        if seg == 0:
            # code fetch in segment 0 comes straight from the ROM
            return (self.rom_data[off + 1] << 8) | self.rom_data[off]
        region = self._lookup(offset)
        if region is None:
            self.chipset.emulator.handle_memory_error()
            return 0
        return (region.read(offset + 1) << 8) | region.read(offset)

    def read_data(self, offset):
        region = self._lookup(offset)
        if region is None:
            self.chipset.emulator.handle_memory_error()
            return 0
        return region.read(offset)

    def write_data(self, offset, data):
        region = self._lookup(offset)
        if region is None:
            self.chipset.emulator.handle_memory_error()
            return
        region.write(offset, data)


# ---------------------------------------------------------------------------
# Convenience region factory helpers (mirror MMURegion static helpers)
# ---------------------------------------------------------------------------
def mem_region(base, size, data_ref):
    """A plain RAM region backed by a bytearray/list 'data_ref' (offset relative)."""
    def rread(region, offset):
        return data_ref[offset - region.base]
    def rwrite(region, offset, data):
        data_ref[offset - region.base] = data
    return Region(base, size, rread, rwrite)


def sfreg_uint(base, size, data_ref, mask=None, on_write=None):
    """An MMIO/SFR region reading/writing a little-endian integer field.

    data_ref : a list-like [value] holding the register value.
    mask     : optional mask applied on write (defaults to all ones).
    on_write : optional callback(data) invoked after storing.
    """
    if mask is None:
        mask = (1 << (8 * size)) - 1

    def rread(region, offset):
        byte_ix = offset - region.base
        return (data_ref[0] >> (byte_ix * 8)) & 0xFF

    def rwrite(region, offset, data):
        byte_ix = offset - region.base
        v = data_ref[0]
        v &= ~(0xFF << (byte_ix * 8))
        v |= (data & 0xFF) << (byte_ix * 8)
        v &= mask
        data_ref[0] = v
        if on_write is not None:
            on_write(data)

    return Region(base, size, rread, rwrite)


def const_region(base, size, value):
    """A read-only region returning a constant byte."""
    def rread(region, offset):
        return value
    def rwrite(region, offset, data):
        pass
    return Region(base, size, rread, rwrite)


def ignore_region(base, size, read_value=0):
    """Ignore reads (return fixed value) and writes."""
    def rread(region, offset):
        return read_value
    def rwrite(region, offset, data):
        pass
    return Region(base, size, rread, rwrite)
############################################################################
# CPU  (cpu.py)
############################################################################
# -*- coding: utf-8 -*-
"""
nX-U8 CPU core, ported from the C++ emulator.

Sources:
  Chipset/CPU.cpp
  Chipset/CPUArithmetic.cpp
  Chipset/CPUControl.cpp
  Chipset/CPULoadStore.cpp
  Chipset/CPUPushPop.cpp

Debug / ROP / Lua hooking code has been removed; only the pure execution
engine is kept.
"""

# PSW status flags (see 1.2.2.1 in the nX-U8 manual)
PSW_C    = 0x80
PSW_Z    = 0x40
PSW_S    = 0x20
PSW_OV   = 0x10
PSW_MIE  = 0x08
PSW_HC   = 0x04
PSW_ELEVEL = 0x03

# Opcode hints
H_IE = 0x0001
H_ST = 0x0002
H_DW = 0x0004
H_DS = 0x0008
H_IA = 0x0010
H_TI = 0x0020
H_WB = 0x0040

MM_SMALL = 0
MM_LARGE = 1


class CPU(object):
    def __init__(self, emulator):
        self.emulator = emulator
        self.chipset = emulator.chipset
        self.memory_model = MM_LARGE

        self.reg_r = [0] * 16
        self.reg_cr = [0] * 16
        self.reg_pc = 0
        self.reg_elr = [0] * 4
        self.reg_csr = 0
        self.reg_ecsr = [0] * 4
        self.reg_epsw = [0] * 4
        self.reg_sp = 0
        self.reg_ea = 0
        self.reg_dsr = 0

        self.impl_last_dsr = 0
        self.impl_flags_changed = 0
        self.impl_flags_out = 0
        self.impl_flags_in = 0
        self.impl_shift_buffer = 0
        self.impl_opcode = 0
        self.impl_long_imm = 0
        self.impl_operands = [{'value': 0, 'register_index': 0, 'register_size': 0},
                              {'value': 0, 'register_index': 0, 'register_size': 0}]
        self.impl_hint = 0
        self.impl_csr_mask = 0

        self.stack = []

        self._setup_opcode_dispatch()

    # ------------------------------------------------------------------
    def _setup_opcode_dispatch(self):
        # Build a compact dispatch table.  The original code used two Python
        # lists of 0x10000 entries (the kept 'dispatch' plus a per-source
        # 'permutation' scratch list); together they need ~512 KB, which blows
        # the HP Prime's MicroPython heap.  A bytearray of 0x10000 bytes is
        # only 64 KB; the scratch list is eliminated entirely by
        # enumerating the don't-care-bit subsets on the fly.
        SENTINEL = 255
        dispatch = bytearray(b'\xff' * 0x10000)
        sources = OPCODE_SOURCES
        if len(sources) >= SENTINEL:
            raise RuntimeError('too many opcode sources for bytearray dispatch')
        for sidx, src in enumerate(sources):
            _func, hint, opcode, operands = src
            varying_bits = 0
            for _size, mask, shift in operands:
                varying_bits |= mask << shift
            base = opcode & ~varying_bits
            # enumerate every value matching the pattern (all subsets of the
            # don't-care bits) without allocating a 64 K scratch list
            sub = 0
            while True:
                idx = base | sub
                if dispatch[idx] == SENTINEL:
                    dispatch[idx] = sidx
                sub = (sub - varying_bits) & varying_bits
                if sub == 0:
                    break
        self.dispatch = dispatch

    def set_memory_model(self, mm):
        self.memory_model = mm

    def reset(self):
        self.reg_sp = self.chipset.mmu.read_code(0)
        self.reg_dsr = 0
        self.reg_epsw[0] = 0
        self.stack = []

    def raise_exception(self, exception_level, index):
        psw = self.reg_epsw[0]
        if exception_level == 1:
            psw &= ~PSW_MIE
        psw = (psw & ~PSW_ELEVEL) | exception_level
        self.reg_epsw[0] = psw
        self.reg_elr[exception_level] = self.reg_pc
        self.reg_ecsr[exception_level] = self.reg_csr
        self.reg_csr = 0
        self.reg_pc = self.chipset.mmu.read_code(index * 2)

    def get_exception_level(self):
        return self.reg_epsw[0] & PSW_ELEVEL

    def get_master_interrupt_enable(self):
        return self.reg_epsw[0] & PSW_MIE

    # ------------------------------------------------------------------
    def _fetch(self):
        csr = self.reg_csr
        if csr & ~self.impl_csr_mask:
            self.reg_csr = csr & self.impl_csr_mask
        pc = self.reg_pc
        if pc & 1:
            self.reg_pc = pc & ~1
        opcode = self.chipset.mmu.read_code((self.reg_csr << 16) | self.reg_pc)
        self.reg_pc = (self.reg_pc + 2) & 0xFFFF
        return opcode

    # ------------------------------------------------------------------
    def next(self):
        reg_epsw = self.reg_epsw
        reg_r = self.reg_r
        dispatch = self.dispatch
        opcodes = OPCODE_SOURCES

        self.reg_dsr = 0
        while True:
            self.impl_opcode = self._fetch()
            opc = self.impl_opcode
            sidx = dispatch[opc]
            if sidx == 255:   # 255 = 'no source' sentinel (see _setup_opcode_dispatch)
                continue
            _func, hint, _code, operands = opcodes[sidx]

            self.impl_long_imm = 0
            if hint & H_TI:
                self.impl_long_imm = self._fetch()

            impl_operands = self.impl_operands
            for ix in (0, 1):
                op_size, op_mask, op_shift = operands[ix]
                op_val = (opc >> op_shift) & op_mask
                reg_index = op_val
                impl_operands[ix]['register_index'] = reg_index
                impl_operands[ix]['register_size'] = op_size
                if op_size:
                    val = 0
                    shift_bx = 0
                    for bx in range(op_size):
                        val |= reg_r[(reg_index + bx) & 15] << shift_bx
                        shift_bx += 8
                    impl_operands[ix]['value'] = val
                else:
                    impl_operands[ix]['value'] = op_val

            self.impl_hint = hint
            self.impl_flags_changed = 0
            self.impl_flags_in = reg_epsw[0]
            self.impl_flags_out = PSW_Z

            getattr(self, _func)()

            reg_epsw[0] &= ~self.impl_flags_changed
            reg_epsw[0] |= self.impl_flags_out & self.impl_flags_changed

            if hint & H_WB and impl_operands[0]['register_size']:
                op0 = impl_operands[0]
                idx = op0['register_index']
                val = op0['value']
                shift_bx = 0
                for bx in range(op0['register_size']):
                    reg_r[(idx + bx) & 15] = (val >> shift_bx) & 0xFF
                    shift_bx += 8

            if not (hint & H_DS):
                break

    # ==================================================================
    def op_add(self):
        self.impl_flags_in &= ~PSW_C
        self.impl_flags_in |= PSW_Z
        self.op_addc()

    def op_add16(self):
        op1 = self.impl_operands[1]
        if self.impl_hint & H_IE:
            op1['value'] |= (op1['value'] & 0x40) and 0xFF80 or 0
        self.impl_flags_in &= ~PSW_C
        op0 = self.impl_operands[0]
        op_high_0 = op0['value'] >> 8
        op_high_1 = op1['value'] >> 8
        self._add8()
        self._zscheck()
        self.impl_flags_in = (self.impl_flags_in & ~PSW_C) | (self.impl_flags_out & PSW_C)
        op_low_0 = op0['value']
        op0['value'] = op_high_0
        op1['value'] = op_high_1
        self._add8()
        self._zscheck()
        op0['value'] = ((op0['value'] << 8) | op_low_0) & 0xFFFF

    def op_addc(self):
        self._add8()
        if not (self.impl_flags_in & PSW_Z):
            self.impl_flags_out &= ~PSW_Z
        self._zscheck()

    def op_and(self):
        self.impl_operands[0]['value'] &= self.impl_operands[1]['value'] & 0xFF
        self._zscheck()

    def op_mov16(self):
        op1 = self.impl_operands[1]
        if self.impl_hint & H_IE:
            op1['value'] |= (op1['value'] & 0x40) and 0xFF80 or 0
        op0 = self.impl_operands[0]
        op0['value'] = op1['value'] & 0xFF
        self._zscheck()
        op_low_0 = op0['value']
        op0['value'] = (op1['value'] >> 8) & 0xFF
        self._zscheck()
        op0['value'] = ((op0['value'] << 8) | op_low_0) & 0xFFFF

    def op_mov(self):
        self.impl_operands[0]['value'] = self.impl_operands[1]['value'] & 0xFF
        self._zscheck()

    def op_or(self):
        self.impl_operands[0]['value'] |= self.impl_operands[1]['value'] & 0xFF
        self._zscheck()

    def op_xor(self):
        self.impl_operands[0]['value'] ^= self.impl_operands[1]['value'] & 0xFF
        self._zscheck()

    def op_cmp16(self):
        self.impl_flags_in &= ~PSW_C
        op0 = self.impl_operands[0]
        op1 = self.impl_operands[1]
        op_high_0 = op0['value'] >> 8
        op_high_1 = op1['value'] >> 8
        op0['value'] ^= 0xFF
        self._add8()
        op0['value'] ^= 0xFF
        self._zscheck()
        self.impl_flags_in = (self.impl_flags_in & ~PSW_C) | (self.impl_flags_out & PSW_C)
        op_low_0 = op0['value']
        op0['value'] = op_high_0
        op1['value'] = op_high_1
        op0['value'] ^= 0xFF
        self._add8()
        op0['value'] ^= 0xFF
        self._zscheck()
        op0['value'] = ((op0['value'] << 8) | op_low_0) & 0xFFFF

    def op_sub(self):
        self.impl_flags_in &= ~PSW_C
        self.impl_flags_in |= PSW_Z
        self.op_subc()

    def op_subc(self):
        self.impl_operands[0]['value'] ^= 0xFF
        self._add8()
        self.impl_operands[0]['value'] ^= 0xFF
        if not (self.impl_flags_in & PSW_Z):
            self.impl_flags_out &= ~PSW_Z
        self._zscheck()

    def op_sll(self):
        self.impl_shift_buffer = 0
        self._shift_left8()

    def op_sllc(self):
        ext = (self.impl_operands[0]['register_index'] - 1) & 15
        self.impl_shift_buffer = self.reg_r[ext]
        self._shift_left8()

    def op_sra(self):
        shift_by = self.impl_operands[1]['value'] & 7
        msb = self.impl_operands[0]['value'] & 0x80
        self.impl_shift_buffer = 0
        self._shift_right8()
        if msb:
            self.impl_operands[0]['value'] |= (0xFF >> shift_by) ^ 0xFF

    def op_srl(self):
        self.impl_shift_buffer = 0
        self._shift_right8()

    def op_srlc(self):
        ext = (self.impl_operands[0]['register_index'] + 1) & 15
        self.impl_shift_buffer = self.reg_r[ext]
        self._shift_right8()

    def op_daa(self):
        op0 = self.impl_operands[0]
        op1 = self.impl_operands[1]
        op1['value'] = 0
        if (op0['value'] & 0x0F) > 0x09 or (self.impl_flags_in & PSW_HC):
            op1['value'] |= 0x06
        if (op0['value'] & 0xF0) > 0x90 or (self.impl_flags_in & PSW_C):
            op1['value'] |= 0x60
        if (op0['value'] & 0xF0) == 0x90 and (op0['value'] & 0x0F) > 0x09 and not (self.impl_flags_in & PSW_HC):
            op1['value'] |= 0x60
        flags_in_backup = self.impl_flags_in
        self.op_add()
        self.impl_flags_out |= flags_in_backup & PSW_C
        self.impl_flags_changed &= ~PSW_OV

    def op_das(self):
        op0 = self.impl_operands[0]
        op1 = self.impl_operands[1]
        op1['value'] = 0
        if (op0['value'] & 0x0F) > 0x09 or (self.impl_flags_in & PSW_HC):
            op1['value'] |= 0x06
        if (op0['value'] & 0xF0) > 0x90 or (self.impl_flags_in & PSW_C):
            op1['value'] |= 0x60
        flags_in_backup = self.impl_flags_in
        self.op_sub()
        self.impl_flags_out |= flags_in_backup & PSW_C
        self.impl_flags_changed &= ~PSW_OV

    def op_neg(self):
        op0 = self.impl_operands[0]
        self.impl_operands[1]['value'] = op0['value']
        op0['value'] = 0
        self.op_sub()

    def op_bitmod(self):
        op0 = self.impl_operands[0]
        bit_in = 1 << self.impl_operands[1]['value']
        if self.impl_hint & H_TI:
            src_index = self.impl_long_imm
            op0['value'] = self.chipset.mmu.read_data(((self.reg_dsr << 16) | src_index) & 0xFFFFFF)
        else:
            src_index = op0['value']
            op0['value'] = self.reg_r[src_index]
        self.impl_flags_changed |= PSW_Z
        self.impl_flags_out = 0 if (op0['value'] & bit_in) else PSW_Z
        opcode_bits = self.impl_opcode & 0x000F
        if opcode_bits == 0:
            op0['value'] |= bit_in
        elif opcode_bits == 2:
            op0['value'] &= ~bit_in
        if opcode_bits != 1:
            if self.impl_hint & H_TI:
                self.chipset.mmu.write_data(((self.reg_dsr << 16) | src_index) & 0xFFFFFF, op0['value'] & 0xFF)
            else:
                self.reg_r[src_index] = op0['value'] & 0xFF

    def op_extbw(self):
        index = (self.impl_opcode & 0x00E0) >> 4
        val = 0xFF if (self.reg_r[index] & 0x80) else 0x00
        self.reg_r[index + 1] = val
        self.impl_operands[0]['value'] = val
        self._zscheck()

    def op_mul(self):
        op0 = self.impl_operands[0]
        op0['value'] = (op0['value'] & 0xFF) * self.impl_operands[1]['value']
        self.impl_flags_changed |= PSW_Z
        self.impl_flags_out = 0 if op0['value'] else PSW_Z

    def op_div(self):
        op0 = self.impl_operands[0]
        div = self.impl_operands[1]['value']
        self.impl_flags_changed |= PSW_Z | PSW_C
        if not div:
            self.impl_flags_out |= PSW_C
            return
        quotient = op0['value'] // div
        remainder = op0['value'] % div
        op0['value'] = quotient
        if op0['value']:
            self.impl_flags_out &= ~PSW_Z
        rr = (self.impl_opcode >> 4) & 0x000F
        self.reg_r[rr] = remainder

    def op_inc_ea(self):
        addr = ((self.reg_dsr << 16) | self.reg_ea) & 0xFFFFFF
        op0 = self.impl_operands[0]
        op0['value'] = self.chipset.mmu.read_data(addr)
        self.impl_operands[1]['value'] = 1
        self.op_add()
        self.impl_flags_changed &= ~PSW_C
        self.chipset.mmu.write_data(addr, op0['value'] & 0xFF)

    def op_dec_ea(self):
        addr = ((self.reg_dsr << 16) | self.reg_ea) & 0xFFFFFF
        op0 = self.impl_operands[0]
        op0['value'] = self.chipset.mmu.read_data(addr)
        self.impl_operands[1]['value'] = 1
        self.op_sub()
        self.impl_flags_changed &= ~PSW_C
        self.chipset.mmu.write_data(addr, op0['value'] & 0xFF)

    def _add8(self):
        op0 = self.impl_operands[0]
        op1 = self.impl_operands[1]
        a = op0['value'] & 0xFF
        b = op1['value'] & 0xFF
        c_in = 1 if (self.impl_flags_in & PSW_C) else 0
        carry_8 = ((a + b + c_in) >> 8) & 1
        carry_7 = (((a & 0x7F) + (b & 0x7F) + c_in) >> 7) & 1
        carry_4 = (((a & 0x0F) + (b & 0x0F) + c_in) >> 4) & 1
        self.impl_flags_changed |= PSW_C | PSW_OV | PSW_HC
        out = self.impl_flags_out
        out = (out & ~PSW_C) | (PSW_C if carry_8 else 0)
        out = (out & ~PSW_OV) | (PSW_OV if (carry_8 ^ carry_7) else 0)
        out = (out & ~PSW_HC) | (PSW_HC if carry_4 else 0)
        self.impl_flags_out = out
        op0['value'] = (a + b + c_in) & 0xFF

    def _zscheck(self):
        self.impl_flags_changed |= PSW_Z | PSW_S
        v = self.impl_operands[0]['value']
        if v & 0xFF:
            self.impl_flags_out &= ~PSW_Z
        self.impl_flags_out = (self.impl_flags_out & ~PSW_S) | (PSW_S if (v & 0x80) else 0)

    def _shift_left8(self):
        op0 = self.impl_operands[0]
        op0['value'] &= 0xFF
        shift_by = self.impl_operands[1]['value'] & 7
        result = op0['value'] << shift_by
        result |= self.impl_shift_buffer >> (8 - shift_by)
        self.impl_flags_changed |= PSW_C
        if result & 0x100:
            self.impl_flags_out |= PSW_C
        op0['value'] = result & 0xFF

    def _shift_right8(self):
        op0 = self.impl_operands[0]
        op0['value'] &= 0xFF
        shift_by = self.impl_operands[1]['value'] & 7
        result = op0['value'] << (8 - shift_by)
        result |= (self.impl_shift_buffer & 0xFF) << (16 - shift_by)
        self.impl_flags_changed |= PSW_C
        if result & 0x80:
            self.impl_flags_out |= PSW_C
        op0['value'] = (result >> 8) & 0xFF

    # ==================================================================
    def op_addsp(self):
        v = self.impl_operands[0]['value']
        if v & 0x80:
            v |= 0xFF00
        self.reg_sp = (self.reg_sp + v) & 0xFFFF
        self.reg_sp &= 0xFFFE

    def op_ctrl(self):
        ctrl = self.impl_hint >> 8
        lvl = self.reg_epsw[0] & PSW_ELEVEL
        op0 = self.impl_operands[0]
        op1 = self.impl_operands[1]
        if ctrl == 1:
            self.reg_ecsr[lvl] = op1['value'] & 0xFFFF
        elif ctrl == 2:
            self.reg_elr[lvl] = op1['value'] & 0xFFFF
        elif ctrl == 3:
            if self.reg_epsw[0] & PSW_ELEVEL:
                self.reg_epsw[lvl] = op1['value'] & 0xFF
        elif ctrl == 4:
            op0['value'] = self.reg_elr[lvl]
        elif ctrl == 5:
            op0['value'] = self.reg_sp
        elif ctrl == 6 or ctrl == 7:
            self.reg_epsw[0] = op1['value'] & 0xFF
        elif ctrl == 8:
            op0['value'] = self.reg_ecsr[lvl]
        elif ctrl == 9:
            if self.reg_epsw[0] & PSW_ELEVEL:
                op0['value'] = self.reg_epsw[lvl]
        elif ctrl == 10:
            op0['value'] = self.reg_epsw[0]
        elif ctrl == 11:
            self.reg_sp = op1['value'] & 0xFFFE

    def op_lea(self):
        self.reg_ea = 0
        if self.impl_operands[1]['register_size']:
            self.reg_ea = (self.reg_ea + self.impl_operands[1]['value']) & 0xFFFF
        if self.impl_hint & H_TI:
            self.reg_ea = (self.reg_ea + self.impl_long_imm) & 0xFFFF

    def op_cr_r(self):
        op0_index = (self.impl_opcode >> 8) & 0x000F
        op1_index = (self.impl_opcode >> 4) & 0x000F
        if self.impl_hint & H_ST:
            self.reg_r[op0_index] = self.reg_cr[op1_index] & 0xFF
        else:
            self.reg_cr[op0_index] = self.reg_r[op1_index] & 0xFF

    def op_cr_ea(self):
        op0_index = (self.impl_opcode >> 8) & 0x000F
        register_size = self.impl_opcode >> 8
        dsr = self.reg_dsr
        ea = self.reg_ea
        mmu = self.chipset.mmu
        reg_cr = self.reg_cr
        if self.impl_hint & H_ST:
            ix = register_size - 1
            while ix != -1:
                mmu.write_data(((dsr << 16) | ((ea + ix) & 0xFFFF)) & 0xFFFFFF, reg_cr[op0_index + ix] & 0xFF)
                ix -= 1
        else:
            ix = 0
            while ix != register_size:
                reg_cr[op0_index + ix] = mmu.read_data(((dsr << 16) | ((ea + ix) & 0xFFFF)) & 0xFFFFFF)
                ix += 1
        if self.impl_hint & H_IA:
            self._bump_ea(register_size)

    def _bump_ea(self, value_size):
        self.reg_ea = (self.reg_ea + value_size) & 0xFFFF
        if value_size != 1:
            self.reg_ea &= ~1

    def op_psw_or(self):
        self.reg_epsw[0] |= (self.impl_opcode & 0xFF)

    def op_psw_and(self):
        self.reg_epsw[0] &= (self.impl_opcode & 0xFF)

    def op_cplc(self):
        self.reg_epsw[0] ^= PSW_C

    def op_bc(self):
        fi = self.impl_flags_in
        c = fi & PSW_C
        z = fi & PSW_Z
        s = fi & PSW_S
        ov = fi & PSW_OV
        le = z | c
        lts = ov ^ s
        les = lts | z
        cond = (self.impl_opcode >> 8) & 0x000F
        if cond == 0:
            branch = not c
        elif cond == 1:
            branch = c
        elif cond == 2:
            branch = not le
        elif cond == 3:
            branch = le
        elif cond == 4:
            branch = not lts
        elif cond == 5:
            branch = lts
        elif cond == 6:
            branch = not les
        elif cond == 7:
            branch = les
        elif cond == 8:
            branch = not z
        elif cond == 9:
            branch = z
        elif cond == 10:
            branch = not ov
        elif cond == 11:
            branch = ov
        elif cond == 12:
            branch = not s
        elif cond == 13:
            branch = s
        else:
            branch = True
        if branch:
            off = self.impl_operands[0]['value']
            if off & 0x80:
                off |= 0x7F00
            self.reg_pc = (self.reg_pc + (off << 1)) & 0xFFFF

    def op_swi(self):
        self.chipset.raise_software(self.impl_operands[0]['value'])

    def op_brk(self):
        self.chipset.break_()

    def op_b(self):
        if self.impl_hint & H_TI:
            self.reg_csr = self.impl_operands[1]['value'] & 0xFFFF
            self.reg_pc = self.impl_long_imm & 0xFFFF
        else:
            self.reg_pc = self.impl_operands[1]['value'] & 0xFFFF

    def op_bl(self):
        self.reg_elr[0] = self.reg_pc
        self.reg_ecsr[0] = self.reg_csr
        self.op_b()
        self.stack.append({'lr_pushed': False, 'lr_push_address': 0,
                           'new_csr': self.reg_csr, 'new_pc': self.reg_pc})

    def op_rt(self):
        if self.stack:
            self.stack.pop()
        self.reg_csr = self.reg_ecsr[0]
        self.reg_pc = self.reg_elr[0]

    def op_rti(self):
        lvl = self.reg_epsw[0] & PSW_ELEVEL
        self.reg_csr = self.reg_ecsr[lvl]
        self.reg_pc = self.reg_elr[lvl]
        self.reg_epsw[0] = self.reg_epsw[lvl]

    def op_ls_ea(self):
        self._load_store(self.reg_ea, self.impl_hint >> 8)

    def op_ls_r(self):
        self._load_store(self.impl_operands[1]['value'], self.impl_hint >> 8)

    def op_ls_i_r(self):
        self._load_store((self.impl_operands[1]['value'] + self.impl_long_imm) & 0xFFFF, self.impl_hint >> 8)

    def op_ls_bp(self):
        op1 = self.impl_operands[1]
        v = op1['value']
        if v & 0x20:
            v |= 0xFFC0
        v += self.reg_r[12] | (self.reg_r[13] << 8)
        self._load_store(v & 0xFFFF, self.impl_hint >> 8)

    def op_ls_fp(self):
        op1 = self.impl_operands[1]
        v = op1['value']
        if v & 0x20:
            v |= 0xFFC0
        v += self.reg_r[14] | (self.reg_r[15] << 8)
        self._load_store(v & 0xFFFF, self.impl_hint >> 8)

    def op_ls_i(self):
        self._load_store(self.impl_long_imm & 0xFFFF, self.impl_hint >> 8)

    def _load_store(self, offset, length):
        if length % 2 == 0:
            offset &= ~1
        reg_base = self.impl_operands[0]['value']
        dsr = self.reg_dsr
        mmu = self.chipset.mmu
        reg_r = self.reg_r
        if self.impl_hint & H_ST:
            ix = length - 1
            while ix != -1:
                mmu.write_data(((dsr << 16) | ((offset + ix) & 0xFFFF)) & 0xFFFFFF, reg_r[reg_base + ix] & 0xFF)
                ix -= 1
        else:
            ix = 0
            while ix != length:
                v = mmu.read_data(((dsr << 16) | ((offset + ix) & 0xFFFF)) & 0xFFFFFF)
                self.impl_operands[0]['value'] = v
                self._zscheck()
                reg_r[reg_base + ix] = v & 0xFF
                ix += 1
        if self.impl_hint & H_IA:
            self._bump_ea(length)

    def op_push(self):
        op1 = self.impl_operands[1]
        push_size = op1['register_size']
        if push_size == 1:
            push_size = 2
        self.reg_sp = (self.reg_sp - push_size) & 0xFFFF
        mmu = self.chipset.mmu
        ix = op1['register_size'] - 1
        while ix != -1:
            mmu.write_data((self.reg_sp + ix) & 0xFFFF, (op1['value'] >> (8 * ix)) & 0xFF)
            ix -= 1

    def op_pushl(self):
        op1 = self.impl_operands[1]
        lvl = self.reg_epsw[0] & PSW_ELEVEL
        mask = op1['value']
        if mask & 2:
            if self.memory_model == MM_LARGE:
                self._push16(self.reg_ecsr[lvl])
            self._push16(self.reg_elr[lvl])
        if mask & 4:
            self._push16(self.reg_epsw[lvl])
        if mask & 8:
            if self.memory_model == MM_LARGE:
                self._push16(self.reg_ecsr[0])
            self._push16(self.reg_elr[0])
            if self.stack:
                fr = self.stack[-1]
                if not fr['lr_pushed']:
                    fr['lr_pushed'] = True
                    fr['lr_push_address'] = self.reg_sp
        if mask & 1:
            self._push16(self.reg_ea)

    def op_pop(self):
        op0 = self.impl_operands[0]
        pop_size = op0['register_size']
        if pop_size == 1:
            pop_size = 2
        op0['value'] = 0
        mmu = self.chipset.mmu
        shift_bx = 0
        for ix in range(op0['register_size']):
            op0['value'] |= mmu.read_data((self.reg_sp + ix) & 0xFFFF) << shift_bx
            shift_bx += 8
        self.reg_sp = (self.reg_sp + pop_size) & 0xFFFF

    def op_popl(self):
        op0 = self.impl_operands[0]
        mask = op0['value']
        if mask & 1:
            self.reg_ea = self._pop16()
        if mask & 8:
            if self.stack:
                fr = self.stack[-1]
                if fr['lr_pushed'] and fr['lr_push_address'] == self.reg_sp:
                    fr['lr_pushed'] = False
            self.reg_elr[0] = self._pop16()
            if self.memory_model == MM_LARGE:
                self.reg_ecsr[0] = self._pop16() & 0x000F
        if mask & 4:
            self.reg_epsw[0] = self._pop16()
        if mask & 2:
            oldsp = self.reg_sp
            self.reg_pc = self._pop16()
            if self.memory_model == MM_LARGE:
                self.reg_csr = self._pop16() & 0x000F
            if self.stack:
                fr = self.stack[-1]
                if fr['lr_pushed'] and fr['lr_push_address'] == oldsp:
                    self.stack.pop()

    def _push16(self, data):
        self.reg_sp = (self.reg_sp - 2) & 0xFFFF
        mmu = self.chipset.mmu
        mmu.write_data((self.reg_sp + 1) & 0xFFFF, (data >> 8) & 0xFF)
        mmu.write_data(self.reg_sp & 0xFFFF, data & 0xFF)

    def _pop16(self):
        mmu = self.chipset.mmu
        result = mmu.read_data(self.reg_sp & 0xFFFF) | (mmu.read_data((self.reg_sp + 1) & 0xFFFF) << 8)
        self.reg_sp = (self.reg_sp + 2) & 0xFFFF
        return result

    def op_nop(self):
        pass

    def op_dsr(self):
        if self.impl_hint & H_DW:
            self.impl_last_dsr = self.impl_operands[0]['value']
        self.reg_dsr = self.impl_last_dsr

OPCODE_SOURCES = [
    ('op_add',   H_WB,              0x8001, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_add',   H_WB,              0x1000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_add16', H_WB,              0xF006, ((2, 0x000E, 8), (2, 0x000E, 4))),
    ('op_add16', H_WB | H_IE,       0xE080, ((2, 0x000E, 8), (0, 0x007F, 0))),
    ('op_addc',  H_WB,              0x8006, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_addc',  H_WB,              0x6000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_and',   H_WB,              0x8002, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_and',   H_WB,              0x2000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_sub',   0,                 0x8007, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_sub',   0,                 0x7000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_subc',  0,                 0x8005, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_subc',  0,                 0x5000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_mov16', H_WB,              0xF005, ((2, 0x000E, 8), (2, 0x000E, 4))),
    ('op_mov16', H_WB | H_IE,       0xE000, ((2, 0x000E, 8), (0, 0x007F, 0))),
    ('op_mov',   H_WB,              0x8000, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_mov',   H_WB,              0x0000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_or',    H_WB,              0x8003, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_or',    H_WB,              0x3000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_xor',   H_WB,              0x8004, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_xor',   H_WB,              0x4000, ((1, 0x000F, 8), (0, 0x00FF, 0))),
    ('op_cmp16', 0,                 0xF007, ((2, 0x000E, 8), (2, 0x000E, 4))),
    ('op_sub',   H_WB,              0x8008, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_subc',  H_WB,              0x8009, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_sll',   H_WB,              0x800A, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_sll',   H_WB,              0x900A, ((1, 0x000F, 8), (0, 0x0007, 4))),
    ('op_sllc',  H_WB,              0x800B, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_sllc',  H_WB,              0x900B, ((1, 0x000F, 8), (0, 0x0007, 4))),
    ('op_sra',   H_WB,              0x800E, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_sra',   H_WB,              0x900E, ((1, 0x000F, 8), (0, 0x0007, 4))),
    ('op_srl',   H_WB,              0x800C, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_srl',   H_WB,              0x900C, ((1, 0x000F, 8), (0, 0x0007, 4))),
    ('op_srlc',  H_WB,              0x800D, ((1, 0x000F, 8), (1, 0x000F, 4))),
    ('op_srlc',  H_WB,              0x900D, ((1, 0x000F, 8), (0, 0x0007, 4))),
    ('op_ls_ea', (2 << 8),          0x9032, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_ls_ea', (2 << 8) | H_IA,   0x9052, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_ls_r',  (2 << 8),          0x9002, ((0, 0x000E, 8), (2, 0x000E, 4))),
    ('op_ls_i_r',(2 << 8) | H_TI,   0xA008, ((0, 0x000E, 8), (2, 0x000E, 4))),
    ('op_ls_bp', (2 << 8),          0xB000, ((0, 0x000E, 8), (0, 0x003F, 0))),
    ('op_ls_fp', (2 << 8),          0xB040, ((0, 0x000E, 8), (0, 0x003F, 0))),
    ('op_ls_i',  (2 << 8) | H_TI,   0x9012, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_ls_ea', (1 << 8),          0x9030, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_ls_ea', (1 << 8) | H_IA,   0x9050, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_ls_r',  (1 << 8),          0x9000, ((0, 0x000F, 8), (2, 0x000E, 4))),
    ('op_ls_i_r',(1 << 8) | H_TI,   0x9008, ((0, 0x000F, 8), (2, 0x000E, 4))),
    ('op_ls_bp', (1 << 8),          0xD000, ((0, 0x000F, 8), (0, 0x003F, 0))),
    ('op_ls_fp', (1 << 8),          0xD040, ((0, 0x000F, 8), (0, 0x003F, 0))),
    ('op_ls_i',  (1 << 8) | H_TI,   0x9010, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_ls_ea', (4 << 8),          0x9034, ((0, 0x000C, 8), (0, 0, 0))),
    ('op_ls_ea', (4 << 8) | H_IA,   0x9054, ((0, 0x000C, 8), (0, 0, 0))),
    ('op_ls_ea', (8 << 8),          0x9036, ((0, 0x0008, 8), (0, 0, 0))),
    ('op_ls_ea', (8 << 8) | H_IA,   0x9056, ((0, 0x0008, 8), (0, 0, 0))),
    ('op_ls_ea', (2 << 8) | H_ST,   0x9033, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_ls_ea', (2 << 8) | H_IA | H_ST, 0x9053, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_ls_r',  (2 << 8) | H_ST,   0x9003, ((0, 0x000E, 8), (2, 0x000E, 4))),
    ('op_ls_i_r',(2 << 8) | H_TI | H_ST, 0xA009, ((0, 0x000E, 8), (2, 0x000E, 4))),
    ('op_ls_bp', (2 << 8) | H_ST,   0xB080, ((0, 0x000E, 8), (0, 0x003F, 0))),
    ('op_ls_fp', (2 << 8) | H_ST,   0xB0C0, ((0, 0x000E, 8), (0, 0x003F, 0))),
    ('op_ls_i',  (2 << 8) | H_TI | H_ST, 0x9013, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_ls_ea', (1 << 8) | H_ST,   0x9031, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_ls_ea', (1 << 8) | H_IA | H_ST, 0x9051, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_ls_r',  (1 << 8) | H_ST,   0x9001, ((0, 0x000F, 8), (2, 0x000E, 4))),
    ('op_ls_i_r',(1 << 8) | H_TI | H_ST, 0x9009, ((0, 0x000F, 8), (2, 0x000E, 4))),
    ('op_ls_bp', (1 << 8) | H_ST,   0xD080, ((0, 0x000F, 8), (0, 0x003F, 0))),
    ('op_ls_fp', (1 << 8) | H_ST,   0xD0C0, ((0, 0x000F, 8), (0, 0x003F, 0))),
    ('op_ls_i',  (1 << 8) | H_TI | H_ST, 0x9011, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_ls_ea', (4 << 8) | H_ST,   0x9035, ((0, 0x000C, 8), (0, 0, 0))),
    ('op_ls_ea', (4 << 8) | H_IA | H_ST, 0x9055, ((0, 0x000C, 8), (0, 0, 0))),
    ('op_ls_ea', (8 << 8) | H_ST,   0x9037, ((0, 0x0008, 8), (0, 0, 0))),
    ('op_ls_ea', (8 << 8) | H_IA | H_ST, 0x9057, ((0, 0x0008, 8), (0, 0, 0))),
    ('op_addsp', 0,                0xE100, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_ctrl',  (1 << 8),         0xA00F, ((0, 0, 0), (1, 0x000F, 4))),
    ('op_ctrl',  (2 << 8),         0xA00D, ((0, 0, 0), (2, 0x000E, 8))),
    ('op_ctrl',  (3 << 8),         0xA00C, ((0, 0, 0), (1, 0x000F, 4))),
    ('op_ctrl',  H_WB | (4 << 8),  0xA005, ((2, 0x000E, 8), (0, 0, 0))),
    ('op_ctrl',  H_WB | (5 << 8),  0xA01A, ((2, 0x000E, 8), (0, 0, 0))),
    ('op_ctrl',  (6 << 8),         0xA00B, ((0, 0, 0), (1, 0x000F, 4))),
    ('op_ctrl',  (7 << 8),         0xE900, ((0, 0, 0), (0, 0x00FF, 0))),
    ('op_ctrl',  H_WB | (8 << 8),  0xA007, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_ctrl',  H_WB | (9 << 8),  0xA004, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_ctrl',  H_WB | (10 << 8), 0xA003, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_ctrl',  (11 << 8),        0xA10A, ((0, 0, 0), (2, 0x000E, 4))),
    ('op_push',  0,                0xF05E, ((0, 0, 0), (2, 0x000E, 8))),
    ('op_push',  0,                0xF07E, ((0, 0, 0), (8, 0x0008, 8))),
    ('op_push',  0,                0xF04E, ((0, 0, 0), (1, 0x000F, 8))),
    ('op_push',  0,                0xF06E, ((0, 0, 0), (4, 0x000C, 8))),
    ('op_pushl', 0,                0xF0CE, ((0, 0, 0), (0, 0x000F, 8))),
    ('op_pop',   H_WB,             0xF01E, ((2, 0x000E, 8), (0, 0, 0))),
    ('op_pop',   H_WB,             0xF03E, ((8, 0x0008, 8), (0, 0, 0))),
    ('op_pop',   H_WB,             0xF00E, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_pop',   H_WB,             0xF02E, ((4, 0x000C, 8), (0, 0, 0))),
    ('op_popl',  0,                0xF08E, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_cr_r',  0,                0xA00E, ((0, 0x000F, 8), (0, 0x000F, 4))),
    ('op_cr_ea', (2 << 8),         0xF02D, ((0, 0, 0), (0, 0x000E, 8))),
    ('op_cr_ea', (2 << 8) | H_IA,  0xF03D, ((0, 0, 0), (0, 0x000E, 8))),
    ('op_cr_ea', (1 << 8),         0xF00D, ((0, 0, 0), (0, 0x000F, 8))),
    ('op_cr_ea', (1 << 8) | H_IA,  0xF01D, ((0, 0, 0), (0, 0x000F, 8))),
    ('op_cr_ea', (4 << 8),         0xF04D, ((0, 0, 0), (0, 0x000C, 8))),
    ('op_cr_ea', (4 << 8) | H_IA,  0xF05D, ((0, 0, 0), (0, 0x000C, 8))),
    ('op_cr_ea', (8 << 8),         0xF06D, ((0, 0, 0), (0, 0x0008, 8))),
    ('op_cr_ea', (8 << 8) | H_IA,  0xF07D, ((0, 0, 0), (0, 0x0008, 8))),
    ('op_cr_r',  H_ST,             0xA006, ((0, 0x000F, 8), (0, 0x000F, 4))),
    ('op_cr_ea', (2 << 8) | H_ST,  0xF0AD, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_cr_ea', (2 << 8) | H_IA | H_ST, 0xF0BD, ((0, 0x000E, 8), (0, 0, 0))),
    ('op_cr_ea', (1 << 8) | H_ST,  0xF08D, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_cr_ea', (1 << 8) | H_IA | H_ST, 0xF09D, ((0, 0x000F, 8), (0, 0, 0))),
    ('op_cr_ea', (4 << 8) | H_ST,  0xF0CD, ((0, 0x000C, 8), (0, 0, 0))),
    ('op_cr_ea', (4 << 8) | H_IA | H_ST, 0xF0DD, ((0, 0x000C, 8), (0, 0, 0))),
    ('op_cr_ea', (8 << 8) | H_ST,  0xF0ED, ((0, 0x0008, 8), (0, 0, 0))),
    ('op_cr_ea', (8 << 8) | H_IA | H_ST, 0xF0FD, ((0, 0x0008, 8), (0, 0, 0))),
    ('op_lea',   0,                0xF00A, ((0, 0, 0), (2, 0x000E, 4))),
    ('op_lea',   H_TI,             0xF00B, ((0, 0, 0), (2, 0x000E, 4))),
    ('op_lea',   H_TI,             0xF00C, ((0, 0, 0), (0, 0, 0))),
    ('op_daa',   H_WB,             0x801F, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_das',   H_WB,             0x803F, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_neg',   H_WB,             0x805F, ((1, 0x000F, 8), (0, 0, 0))),
    ('op_bitmod', 0,               0xA000, ((0, 0x000F, 8), (0, 0x0007, 4))),
    ('op_bitmod', H_TI,            0xA080, ((0, 0, 0), (0, 0x0007, 4))),
    ('op_bitmod', 0,               0xA002, ((0, 0x000F, 8), (0, 0x0007, 4))),
    ('op_bitmod', H_TI,            0xA082, ((0, 0, 0), (0, 0x0007, 4))),
    ('op_bitmod', 0,               0xA001, ((0, 0x000F, 8), (0, 0x0007, 4))),
    ('op_bitmod', H_TI,            0xA081, ((0, 0, 0), (0, 0x0007, 4))),
    ('op_psw_or', 0,               0xED08, ((0, 0, 0), (0, 0, 0))),
    ('op_psw_and', 0,              0xEBF7, ((0, 0, 0), (0, 0, 0))),
    ('op_psw_or', 0,               0xED80, ((0, 0, 0), (0, 0, 0))),
    ('op_psw_and', 0,              0xEB7F, ((0, 0, 0), (0, 0, 0))),
    ('op_cplc',   0,               0xFECF, ((0, 0, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC000, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC100, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC200, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC300, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC400, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC500, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC600, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC700, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC800, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xC900, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xCA00, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xCB00, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xCC00, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xCD00, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_bc',    0,                0xCE00, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x810F, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x832F, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x854F, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x876F, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x898F, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x8BAF, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x8DCF, ((0, 0, 0), (0, 0, 0))),
    ('op_extbw', 0,                0x8FEF, ((0, 0, 0), (0, 0, 0))),
    ('op_swi',   0,                0xE500, ((0, 0x003F, 0), (0, 0, 0))),
    ('op_brk',   0,                0xFFFF, ((0, 0, 0), (0, 0, 0))),
    ('op_b',     H_TI,             0xF000, ((0, 0, 0), (0, 0x000F, 8))),
    ('op_b',     0,                0xF002, ((0, 0, 0), (2, 0x000E, 4))),
    ('op_bl',    H_TI,             0xF001, ((0, 0, 0), (0, 0x000F, 8))),
    ('op_bl',    0,                0xF003, ((0, 0, 0), (2, 0x000E, 4))),
    ('op_mul',   H_WB,             0xF004, ((2, 0x000E, 8), (1, 0x000F, 4))),
    ('op_div',   H_WB,             0xF009, ((2, 0x000E, 8), (1, 0x000F, 4))),
    ('op_inc_ea', 0,               0xFE2F, ((0, 0, 0), (0, 0, 0))),
    ('op_dec_ea', 0,               0xFE3F, ((0, 0, 0), (0, 0, 0))),
    ('op_rt',     0,               0xFE1F, ((0, 0, 0), (0, 0, 0))),
    ('op_rti',    0,               0xFE0F, ((0, 0, 0), (0, 0, 0))),
    ('op_nop',    0,               0xFE8F, ((0, 0, 0), (0, 0, 0))),
    ('op_dsr',    H_DS,            0xFE9F, ((0, 0, 0), (0, 0, 0))),
    ('op_dsr',    H_DS | H_DW,     0xE300, ((0, 0x00FF, 0), (0, 0, 0))),
    ('op_dsr',    H_DS | H_DW,     0x900F, ((1, 0x000F, 4), (0, 0, 0))),
]
############################################################################
# PERIPHERALS  (peripherals.py)
############################################################################
# -*- coding: utf-8 -*-
"""
Peripheral devices for the fx-991CN X (ClassWiz) emulator.

Ported from the C++ emulator (Peripheral/*.cpp + Chipset/InterruptSource.cpp).
Only the logic needed for a basic calculator is kept: ROM window, battery
backed RAM, screen framebuffer + SFRs, keyboard, standby control,
miscellaneous registers and the timer.  Debug / ROP features are omitted.
"""




class InterruptSource(object):
    """A peripheral interrupt source (Ported from Chipset/InterruptSource.cpp)."""
    def __init__(self):
        self.interrupt_index = 0
        self.emulator = None
        self.raise_success = False

    def setup(self, interrupt_index, emulator):
        self.interrupt_index = interrupt_index
        self.emulator = emulator

    def enabled(self):
        return self.emulator.chipset.interrupt_enabled_by_sfr(self.interrupt_index)

    def try_raise(self):
        chipset = self.emulator.chipset
        if not chipset.interrupt_enabled_by_sfr(self.interrupt_index) or \
           chipset.get_interrupt_pending_sfr(self.interrupt_index):
            self.raise_success = False
        else:
            chipset.raise_maskable(self.interrupt_index)
            self.raise_success = True
        return self.raise_success

    def success(self):
        return self.raise_success and self.emulator.chipset.get_interrupt_pending_sfr(self.interrupt_index)



class Peripheral(object):
    def __init__(self, chipset):
        self.chipset = chipset
        self.emulator = chipset.emulator
        self.require_frame = False

    def initialise(self):
        pass

    def tick(self):
        pass

    def tick_after_interrupts(self):
        pass

    def frame(self):
        pass

    def reset(self):
        pass


# ---------------------------------------------------------------------------
# ROM window
# ---------------------------------------------------------------------------
class ROMWindow(Peripheral):
    def initialise(self):
        hwid = self.emulator.hardware_id
        mmu = self.chipset.mmu
        rom = self.chipset.rom_data
        strict_memory = getattr(self.emulator, 'strict_memory', False)
        # (region_base, size, rom_base)
        if hwid == 3:      # HW_ES_PLUS
            segs = [(0x00000, 0x08000, 0x00000),
                    (0x10000, 0x10000, 0x10000),
                    (0x80000, 0x10000, 0x00000)]
        elif hwid == 4:    # HW_CLASSWIZ  (fx-991CN X)
            segs = [(0x00000, 0x0D000, 0x00000),
                    (0x10000, 0x10000, 0x10000),
                    (0x20000, 0x10000, 0x20000),
                    (0x30000, 0x10000, 0x30000),
                    (0x50000, 0x10000, 0x00000)]
        else:              # HW_CLASSWIZ_II
            segs = [(0x00000, 0x09000, 0x00000),
                    (0x10000, 0x10000, 0x10000),
                    (0x20000, 0x10000, 0x20000),
                    (0x30000, 0x10000, 0x30000),
                    (0x40000, 0x10000, 0x40000),
                    (0x50000, 0x10000, 0x50000),
                    (0x70000, 0x10000, 0x70000),
                    (0x80000, 0x08E00, 0x00000)]

        def make_region(rbase, size, rbase_rom, offset):
            # data = rom slice view
            def rread(region, address):
                return rom[address - region.base + offset]
            def rwrite(region, address, data):
                # default: writes to ROM are ignored
                pass
            return Region(rbase, size, rread, rwrite)

        for (rbase, size, rom_base) in segs:
            offset = rom_base - rbase
            if rom_base + size > len(rom):
                raise Exception('Invalid ROM region base %x size %x' % (rom_base, size))
            mmu.register_region(make_region(rbase, size, rom_base, offset))


# ---------------------------------------------------------------------------
# Battery backed RAM
# ---------------------------------------------------------------------------
class BatteryBackedRAM(Peripheral):
    def initialise(self):
        hwid = self.emulator.hardware_id
        if hwid == 3:
            self.ram_size = 0xE00
            base = 0x8000
        elif hwid == 4:
            self.ram_size = 0x2000
            base = 0xD000
        else:
            self.ram_size = 0x6000
            base = 0x9000
        real_hw = real_hardware
        if not real_hw:
            self.ram_size += 0x100

        self.ram_buffer = bytearray(self.ram_size)  # all zero

        mmu = self.chipset.mmu
        mmu.register_region(mem_region(base, self.ram_size, self.ram_buffer))
        if not real_hw:
            if hwid == 3:
                base2 = 0x9800
            elif hwid == 4:
                base2 = 0x49800
            else:
                base2 = 0x89800
            # the extra 0x100 region aliases the tail of the ram buffer
            # we keep a separate bytearray so it is independent
            self.ram_tail = bytearray(self.ram_buffer[self.ram_size - 0x100:])
            mmu.register_region(mem_region(base2, 0x100, self.ram_tail))


# ---------------------------------------------------------------------------
# Screen (state + SFRs).  Rendering is done by the hpprime display layer.
# ---------------------------------------------------------------------------
class Screen(Peripheral):
    def initialise(self):
        hwid = self.emulator.hardware_id
        self.n_row = N_ROW
        self.row_size = ROW_SIZE
        self.offset = OFFSET
        self.row_size_disp = ROW_SIZE_DISP
        self.screen_size = (self.n_row + 1) * self.row_size
        self.screen_buffer = bytearray(self.screen_size)
        self.screen_mode = 0
        self.screen_range = 0
        self.screen_contrast = 8
        self.require_frame = True

        mmu = self.chipset.mmu
        buf = self.screen_buffer
        rs = self.row_size
        rsc = self.row_size_disp

        def rread(region, address):
            o = address - region.base
            if (o % rs) >= rsc:
                return 0
            return buf[o]
        def rwrite(region, address, data):
            o = address - region.base
            if (o % rs) >= rsc:
                return
            if buf[o] != data:
                self.require_frame = True
                buf[o] = data
        mmu.register_region(Region(screen_base, self.screen_size, rread, rwrite))

        # screen mode / range / contrast
        def mode_read(region, address):
            return self.screen_mode & 0x07
        def mode_write(region, address, data):
            v = data & 0x07
            if v != self.screen_mode:
                self.screen_mode = v
                self.require_frame = True
        def range_read(region, address):
            return self.screen_range & 0x07
        def range_write(region, address, data):
            v = data & 0x07
            if v != self.screen_range:
                self.screen_range = v
                self.require_frame = True
        def contrast_read(region, address):
            return self.screen_contrast & 0x3F
        def contrast_write(region, address, data):
            v = data & 0x3F
            if v != self.screen_contrast:
                self.screen_contrast = v
                self.require_frame = True
        mmu.register_region(Region(0xF031, 1, mode_read, mode_write))
        mmu.register_region(Region(0xF030, 1, range_read, range_write))
        mmu.register_region(Region(0xF032, 1, contrast_read, contrast_write))

    def frame(self):
        self.require_frame = False


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------
class Keyboard(Peripheral):
    BT_NONE = 0
    BT_BUTTON = 1
    BT_POWER = 2

    def initialise(self):
        self.require_frame = True
        self.interrupt_source = InterruptSource()
        self.interrupt_source.setup(5, self.emulator)

        self.keyboard_in = 0
        self.input_filter = 0
        self.keyboard_out = 0
        self.keyboard_out_mask = 0
        self.keyboard_ghost = [0] * 8
        self.has_input = 0

        mmu = self.chipset.mmu

        # KI (read-only)
        def ki_read(region, address):
            return self.keyboard_in
        def ki_write(region, address, data):
            pass
        mmu.register_region(Region(0xF040, 1, ki_read, ki_write))

        # input filter
        def if_read(region, address):
            return self.input_filter
        def if_write(region, address, data):
            self.input_filter = data
        mmu.register_region(Region(0xF042, 1, if_read, if_write))

        # KO mask
        def kom_read(region, address):
            o = address - region.base
            return (self.keyboard_out_mask & 0x03FF) >> (o * 8)
        def kom_write(region, address, data):
            o = address - region.base
            self.keyboard_out_mask &= ~(0xFF << (o * 8))
            self.keyboard_out_mask |= (data & 0xFF) << (o * 8)
            self.keyboard_out_mask &= 0x03FF
            if o == 0:
                self.recalculate_ki()
        mmu.register_region(Region(0xF044, 2, kom_read, kom_write))

        # KO
        def ko_read(region, address):
            o = address - region.base
            return (self.keyboard_out & 0x03FF) >> (o * 8)
        def ko_write(region, address, data):
            o = address - region.base
            self.keyboard_out &= ~(0xFF << (o * 8))
            self.keyboard_out |= (data & 0xFF) << (o * 8)
            self.keyboard_out &= 0x03FF
            if o == 0:
                self.recalculate_ki()
        mmu.register_region(Region(0xF046, 2, ko_read, ko_write))

        # emulator-mode keyboard shadow registers
        if not real_hardware:
            self.keyboard_ready_emu = 0
            self.keyboard_out_emu = 0
            self.keyboard_in_emu = 0
            self.keyboard_pd_emu = pd_value
            base = 0x40000 if self.emulator.hardware_id == 4 else \
                   (0 if self.emulator.hardware_id == 3 else 0x80000)
            def rdy_read(region, address):
                return self.keyboard_ready_emu
            def rdy_write(region, address, data):
                self.keyboard_ready_emu = data
            mmu.register_region(Region(base + 0x8E00, 1, rdy_read, rdy_write))
            def kiem_read(region, address):
                return self.keyboard_in_emu
            def kiem_write(region, address, data):
                pass
            mmu.register_region(Region(base + 0x8E01, 1, kiem_read, kiem_write))
            def koem_read(region, address):
                return self.keyboard_out_emu
            def koem_write(region, address, data):
                pass
            mmu.register_region(Region(base + 0x8E02, 1, koem_read, koem_write))
            def pd_read(region, address):
                return self.keyboard_pd_emu
            def pd_write(region, address, data):
                pass
            mmu.register_region(Region(0xF050, 1, pd_read, pd_write))

        # build buttons from the model button_map
        self.buttons = [{'type': self.BT_NONE, 'rect': (0, 0, 0, 0),
                         'ko_bit': 0, 'ki_bit': 0, 'pressed': False, 'stuck': False}
                        for _ in range(64)]
        self.buttons_by_name = {}
        for (x, y, w, h, code, name) in button_map:
            if code == 0xFF:
                button_ix = 63
            else:
                button_ix = ((code >> 1) & 0x38) | (code & 0x07)
            b = self.buttons[button_ix]
            if code == 0xFF:
                b['type'] = self.BT_POWER
            else:
                b['type'] = self.BT_BUTTON
            b['rect'] = (x, y, w, h)
            b['ko_bit'] = 1 << ((code >> 4) & 0xF)
            b['ki_bit'] = 1 << (code & 0xF)
            b['pressed'] = False
            b['stuck'] = False
            self.buttons_by_name[name] = button_ix

    def reset(self):
        self.p0 = False
        self.p1 = False
        self.p146 = False
        self.keyboard_out = 0
        self.keyboard_out_mask = 0
        if not real_hardware:
            self.keyboard_in_emu = 0
            self.keyboard_out_emu = 0
        self.recalculate_ghost()

    def tick(self):
        if self.has_input and self.interrupt_source.enabled():
            self.interrupt_source.try_raise()

    def frame(self):
        self.require_frame = False

    def press_button(self, button_ix, stick=False):
        b = self.buttons[button_ix]
        old_pressed = b['pressed']
        if stick:
            b['stuck'] = not b['stuck']
            b['pressed'] = b['stuck']
        else:
            b['pressed'] = True
        self.require_frame = True
        if b['type'] == self.BT_POWER and b['pressed'] and not old_pressed:
            self.chipset.reset()
        if b['type'] == self.BT_BUTTON and b['pressed'] != old_pressed:
            if real_hardware:
                self.recalculate_ghost()
            else:
                if b['pressed']:
                    self.has_input = b['ki_bit']
                    self.keyboard_in_emu = b['ki_bit']
                    self.keyboard_out_emu = b['ko_bit']
                else:
                    self.has_input = 0
                    self.keyboard_in_emu = 0
                    self.keyboard_out_emu = 0

    def press_at(self, x, y, stick=False):
        for b in self.buttons:
            rx, ry, rw, rh = b['rect']
            if rx <= x < rx + rw and ry <= y < ry + rh:
                self.press_button(self.buttons.index(b), stick)
                break

    def release_all(self):
        had_effect = False
        for b in self.buttons:
            if not b['stuck'] and b['pressed']:
                b['pressed'] = False
                if b['type'] == self.BT_BUTTON:
                    had_effect = True
        if had_effect:
            self.require_frame = True
            if real_hardware:
                self.recalculate_ghost()
            else:
                self.has_input = 0
                self.keyboard_in_emu = 0
                self.keyboard_out_emu = 0

    def recalculate_ghost(self):
        # columns
        columns = [{'connections': 0, 'seen': False} for _ in range(8)]
        self.has_input = 0
        for b in self.buttons:
            if b['type'] == self.BT_BUTTON and b['pressed'] and (b['ki_bit'] & self.input_filter):
                self.has_input |= b['ki_bit']
        for cx in range(8):
            for rx in range(8):
                b = self.buttons[cx * 8 + rx]
                if b['type'] == self.BT_BUTTON and b['pressed']:
                    for ax in range(8):
                        sibling = self.buttons[ax * 8 + rx]
                        if sibling['type'] == self.BT_BUTTON and sibling['pressed']:
                            columns[cx]['connections'] |= 1 << ax
        for cx in range(8):
            if not columns[cx]['seen']:
                to_visit = 1 << cx
                ghost_mask = 1 << cx
                columns[cx]['seen'] = True
                while to_visit:
                    new_to_visit = 0
                    for vx in range(8):
                        if to_visit & (1 << vx):
                            for sx in range(8):
                                if (columns[vx]['connections'] & (1 << sx)) and not columns[sx]['seen']:
                                    new_to_visit |= 1 << sx
                                    ghost_mask |= 1 << sx
                                    columns[sx]['seen'] = True
                    to_visit = new_to_visit
                for gx in range(8):
                    if ghost_mask & (1 << gx):
                        self.keyboard_ghost[gx] = ghost_mask
        self.recalculate_ki()

    def recalculate_ki(self):
        keyboard_out_ghosted = 0
        for ix in range(7):
            if self.keyboard_out & ~self.keyboard_out_mask & (1 << ix):
                keyboard_out_ghosted |= self.keyboard_ghost[ix]
        self.keyboard_in = 0xFF
        for b in self.buttons:
            if b['type'] == self.BT_BUTTON and b['pressed'] and (b['ko_bit'] & keyboard_out_ghosted):
                self.keyboard_in &= ~b['ki_bit']
        if (self.keyboard_out & ~self.keyboard_out_mask & (1 << 7)) and self.p0:
            self.keyboard_in &= 0x7F
        if (self.keyboard_out & ~self.keyboard_out_mask & (1 << 8)) and self.p1:
            self.keyboard_in &= 0x7F
        if (self.keyboard_out & ~self.keyboard_out_mask & (1 << 9)) and self.p146:
            self.keyboard_in &= 0x7F


# ---------------------------------------------------------------------------
# Standby control
# ---------------------------------------------------------------------------
class StandbyControl(Peripheral):
    def initialise(self):
        self.stpacp_last = 0
        self.stop_acceptor_enabled = False

        def stp_read(region, address):
            return 0
        def stp_write(region, address, data):
            if (data & 0xF0) == 0xA0 and (self.stpacp_last & 0xF0) == 0x50:
                self.stop_acceptor_enabled = True
            self.stpacp_last = data
        self.chipset.mmu.register_region(Region(0xF008, 1, stp_read, stp_write))

        def sby_read(region, address):
            return 0
        def sby_write(region, address, data):
            if data & 0x01:
                self.chipset.halt()
                return
            if (data & 0x02) and self.stop_acceptor_enabled:
                self.stop_acceptor_enabled = False
                self.chipset.stop()
                return
        self.chipset.mmu.register_region(Region(0xF009, 1, sby_read, sby_write))

    def reset(self):
        self.stpacp_last = 0
        self.stop_acceptor_enabled = False


# ---------------------------------------------------------------------------
# Miscellaneous registers
# ---------------------------------------------------------------------------
class Miscellaneous(Peripheral):
    UNKNOWN_ADDRS = [0xF00A, 0xF018, 0xF033, 0xF034, 0xF041,
                      0xF012, 0xF03D, 0xF224, 0xF028, 0xF310, 0xF037]

    def initialise(self):
        mmu = self.chipset.mmu
        cpu = self.chipset.cpu
        # DSR register
        def dsr_read(region, address):
            return cpu.reg_dsr
        def dsr_write(region, address, data):
            cpu.reg_dsr = data
        mmu.register_region(Region(0xF000, 1, dsr_read, dsr_write))

        # unknown bytes
        addrs = self.UNKNOWN_ADDRS
        self.data = {}
        for a in addrs:
            def mkread(a=a):
                def r(region, address):
                    return self.data.get(a, 0) & 0xFF
                return r
            def mkwrite(a=a):
                def w(region, address, data):
                    self.data[a] = data
                return w
            mmu.register_region(Region(a, 1, mkread(a), mkwrite(a)))

        # F048        # F048: 8-byte field
        self.data_f048 = 0
        def f048_read(region, address):
            return (self.data_f048 >> ((address - region.base) * 8)) & 0xFF
        def f048_write(region, address, data):
            o = (address - region.base) * 8
            self.data_f048 &= ~(0xFF << o)
            self.data_f048 |= (data & 0xFF) << o
        mmu.register_region(Region(0xF048, 8, f048_read, f048_write))

        # F220: 4-byte field
        self.data_f220 = 0
        def f220_read(region, address):
            return (self.data_f220 >> ((address - region.base) * 8)) & 0xFF
        def f220_write(region, address, data):
            o = (address - region.base) * 8
            self.data_f220 &= ~(0xFF << o)
            self.data_f220 |= (data & 0xFF) << o
        mmu.register_region(Region(0xF220, 4, f220_read, f220_write))


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------
class Timer(Peripheral):
    def initialise(self):
        self.interrupt_source = InterruptSource()
        self.interrupt_source.setup(9, self.emulator)
        self.real_hardware = real_hardware
        self.timer_skipped = False
        self.data_interval = 1
        self.data_counter = 0
        self.data_control = 0
        self.data_f024 = 0
        self.raise_required = False
        self.ext_to_int_counter = 0
        self.ext_to_int_next = 0
        self.ext_to_int_int_done = 0
        self.ext_to_int_frequency = 4

        mmu = self.chipset.mmu
        # interval (write clamps to >=1)
        def iv_read(region, address):
            return (self.data_interval >> ((address - region.base) * 8)) & 0xFF
        def iv_write(region, address, data):
            o = (address - region.base) * 8
            self.data_interval &= ~(0xFF << o)
            self.data_interval |= (data & 0xFF) << o
            if self.data_interval == 0:
                self.data_interval = 1
        mmu.register_region(Region(0xF020, 2, iv_read, iv_write))

        # counter (write clears)
        def ct_read(region, address):
            return (self.data_counter >> ((address - region.base) * 8)) & 0xFF
        def ct_write(region, address, data):
            self.data_counter = 0
        mmu.register_region(Region(0xF022, 2, ct_read, ct_write))

        # control
        def ctl_read(region, address):
            return self.data_control & 0x01
        def ctl_write(region, address, data):
            self.data_control = data & 0x01
            self.raise_required = False
            self.timer_skipped = False
        mmu.register_region(Region(0xF025, 1, ctl_read, ctl_write))

        # unknown F024
        mmu.register_region(sfreg_uint(0xF024, 1, [self.data_f024]))

    def reset(self):
        self.ext_to_int_counter = 0
        self.ext_to_int_next = 0
        self.ext_to_int_int_done = 0
        self.divide_ticks()
        self.raise_required = False
        self.timer_skipped = False
        self.data_control = 0

    def tick(self):
        if self.ext_to_int_counter == self.ext_to_int_next:
            self.divide_ticks()
        self.ext_to_int_counter += 1
        if self.raise_required:
            self.interrupt_source.try_raise()

    def tick_after_interrupts(self):
        if self.raise_required and self.interrupt_source.success():
            self.raise_required = False
            self.timer_skipped = False

    def divide_ticks(self):
        if self.emulator.hardware_id == 5 and not self.real_hardware and \
           not self.chipset.get_running_state():
            # CLASSWIZ_II keyboard-ready emulation only; not used for fx-991CN X
            pass
        self.ext_to_int_int_done += 1
        if self.ext_to_int_int_done == self.ext_to_int_frequency:
            self.ext_to_int_int_done = 0
            self.ext_to_int_counter = 0
        cps = cycles_per_second
        self.ext_to_int_next = cps * (self.ext_to_int_int_done + 1) // self.ext_to_int_frequency
        if self.data_control & 0x01:
            if self.data_counter == (1 if self.timer_skipped else self.data_interval):
                self.data_counter = 0
                if self.interrupt_source.enabled():
                    self.raise_required = True
            self.data_counter += 1
############################################################################
# CHIPSET  (chipset.py)
############################################################################
# -*- coding: utf-8 -*-
"""
Chipset: owns the CPU, MMU, ROM image and the peripheral set, and manages
interrupts / run state.

Ported from the C++ emulator (Chipset/Chipset.cpp, Chipset/InterruptSource.cpp).
Debug / ROP / Lua hooking code has been removed.
"""


# Interrupt indices
INT_CHECKFLAG = 0
INT_RESET = 1
INT_BREAK = 2
INT_EMULATOR = 3
INT_NONMASKABLE = 4
INT_MASKABLE = 5
INT_SOFTWARE = 64
INT_COUNT = 128

RM_STOP = 0
RM_HALT = 1
RM_RUN = 2

managed_interrupt_base = 4
managed_interrupt_amount = 13
interrupt_bitfield_mask = (1 << managed_interrupt_amount) - 1



class Chipset(object):
    def __init__(self, emulator):
        self.emulator = emulator
        emulator.chipset = self
        self.rom_data = bytearray(0)
        self.cpu = CPU(emulator)
        self.mmu = MMU(self)
        self.peripherals = []
        self.run_mode = RM_STOP
        self.pending_interrupt_count = 0
        self.interrupts_active = [False] * INT_COUNT
        self.data_int_mask = 0
        self.data_int_pending = 0
        self.cpu.impl_csr_mask = csr_mask

    # ------------------------------------------------------------------
    def setup(self):
        self.cpu.set_memory_model(MM_LARGE)
        self.construct_peripherals()

    # model module constants: import CPU.MM_LARGE as MM_LARGE
    # We re-import below to keep module import order sane.

    def construct_peripherals(self):
        hwid = self.emulator.hardware_id
        self.peripherals.append(ROMWindow(self))
        self.peripherals.append(BatteryBackedRAM(self))
        self.peripherals.append(Screen(self))
        self.peripherals.append(Keyboard(self))
        self.peripherals.append(StandbyControl(self))
        self.peripherals.append(Miscellaneous(self))
        self.peripherals.append(Timer(self))

    def setup_internals(self):
        # load the ROM image from the external resource file
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, rom_path)
        with open(path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        # the ROM data is read through the MMU's rom_data reference; point it here
        self.mmu.rom_data = self.rom_data

        for p in self.peripherals:
            p.initialise()

        self.construct_interrupt_sfr()

        self.cpu._setup_opcode_dispatch()  # csr_mask already set
        self.cpu.set_memory_model(MM_LARGE)

    # ------------------------------------------------------------------
    def construct_interrupt_sfr(self):
        def mask_read(region, offset):
            byte_ix = offset - region.base
            return (self.data_int_mask >> (byte_ix * 8)) & 0xFF
        def mask_write(region, offset, data):
            byte_ix = offset - region.base
            self.data_int_mask &= ~(0xFF << (byte_ix * 8))
            self.data_int_mask |= (data & 0xFF) << (byte_ix * 8)
            self.data_int_mask &= interrupt_bitfield_mask
        def pend_read(region, offset):
            byte_ix = offset - region.base
            return (self.data_int_pending >> (byte_ix * 8)) & 0xFF
        def pend_write(region, offset, data):
            byte_ix = offset - region.base
            self.data_int_pending &= ~(0xFF << (byte_ix * 8))
            self.data_int_pending |= (data & 0xFF) << (byte_ix * 8)
            self.data_int_pending &= interrupt_bitfield_mask
        self.mmu.register_region(Region(0xF010, 2, mask_read, mask_write))
        self.mmu.register_region(Region(0xF014, 2, pend_read, pend_write))

    # ------------------------------------------------------------------
    def reset(self):
        self.data_int_mask = 0
        self.data_int_pending = 0
        for p in self.peripherals:
            p.reset()
        self.cpu.reset()
        self.interrupts_active = [False] * INT_COUNT
        self.interrupts_active[INT_RESET] = True
        self.pending_interrupt_count = 1
        self.run_mode = RM_RUN

    def break_(self):
        if self.cpu.get_exception_level() > 1:
            self.reset()
            return
        if self.interrupts_active[INT_BREAK]:
            return
        self.interrupts_active[INT_BREAK] = True
        self.pending_interrupt_count += 1

    def halt(self):
        self.run_mode = RM_HALT

    def stop(self):
        self.run_mode = RM_STOP

    def get_running_state(self):
        return self.run_mode == RM_RUN

    def raise_emulator(self):
        if self.interrupts_active[INT_EMULATOR]:
            return
        self.interrupts_active[INT_EMULATOR] = True
        self.pending_interrupt_count += 1

    def raise_nonmaskable(self):
        if self.interrupts_active[INT_NONMASKABLE]:
            return
        self.interrupts_active[INT_NONMASKABLE] = True
        self.pending_interrupt_count += 1

    def raise_maskable(self, index):
        if index < INT_MASKABLE or index >= INT_SOFTWARE:
            raise Exception('%d is not a valid maskable interrupt index' % index)
        if self.interrupts_active[index]:
            return
        self.interrupts_active[index] = True
        self.pending_interrupt_count += 1

    def raise_software(self, index):
        index += 0x40
        if self.interrupts_active[index]:
            return
        self.interrupts_active[index] = True
        self.pending_interrupt_count += 1

    def _accept_interrupt(self):
        old_exception_level = self.cpu.get_exception_level()
        index = 0
        if self.interrupts_active[INT_RESET]:
            index = INT_RESET
        if not index:
            ix = INT_SOFTWARE
            while ix != INT_COUNT:
                if self.interrupts_active[ix]:
                    if old_exception_level > 1:
                        raise Exception('software interrupt while exception level > 1')
                    index = ix
                    break
                ix += 1
        if not index and self.interrupts_active[INT_EMULATOR]:
            index = INT_EMULATOR
        if not index and self.interrupts_active[INT_BREAK]:
            index = INT_BREAK
        if not index and self.interrupts_active[INT_NONMASKABLE] and old_exception_level <= 2:
            index = INT_NONMASKABLE
        if not index and old_exception_level <= 1:
            ix = INT_MASKABLE
            while ix != INT_SOFTWARE:
                if self.interrupts_active[ix]:
                    index = ix
                    break
                ix += 1

        if index == INT_RESET:
            exception_level = 0
        elif index == INT_BREAK or index == INT_NONMASKABLE:
            exception_level = 2
        elif index == INT_EMULATOR:
            exception_level = 3
        else:
            exception_level = 1

        if index >= INT_MASKABLE and index < INT_SOFTWARE:
            if self.interrupt_enabled_by_sfr(index):
                self.set_interrupt_pending_sfr(index)
                if self.cpu.get_master_interrupt_enable():
                    self.cpu.raise_exception(exception_level, index)
        else:
            self.cpu.raise_exception(exception_level, index)

        self.run_mode = RM_RUN
        self.interrupts_active[index] = False
        self.pending_interrupt_count -= 1

    def interrupt_enabled_by_sfr(self, index):
        return self.data_int_mask & (1 << (index - managed_interrupt_base))

    def get_interrupt_pending_sfr(self, index):
        return self.data_int_pending & (1 << (index - managed_interrupt_base))

    def set_interrupt_pending_sfr(self, index):
        self.data_int_pending |= (1 << (index - managed_interrupt_base))

    # ------------------------------------------------------------------
    def get_require_frame(self):
        for p in self.peripherals:
            if p.require_frame:
                return True
        return False

    def frame(self):
        for p in self.peripherals:
            p.frame()

    def tick(self):
        for p in self.peripherals:
            p.tick()
        if self.pending_interrupt_count:
            self._accept_interrupt()
        for p in self.peripherals:
            p.tick_after_interrupts()
        if self.run_mode == RM_RUN:
            self.cpu.next()
############################################################################
# DISPLAY  (display.py)
############################################################################
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



# HP Prime screen size
_SCREEN_W = 320
_SCREEN_H = 240

# LCD dot-matrix geometry (fx-991CN X, CLASSWIZ)
_LCD_W = ROW_SIZE_DISP * 8          # 24 * 8 = 192
_LCD_H = N_ROW                       # 63

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
            for (label, off, m) in status_indicators:
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
            for (label, off, m) in status_indicators:
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
############################################################################
# EMU  (emu.py)
############################################################################
# -*- coding: utf-8 -*-
"""
Main emulator object for the fx-991CN X (ClassWiz) running on the HP Prime.

Ported from the C++ CasioEmuNeo Emulator.cpp + Emulator.hpp.  All the Lua,
debug, ROP and injection machinery has been removed.  The loop is frame driven:
run a batch of machine cycles, refresh the LCD through hpprime, then sample the
keyboard (also through hpprime).
"""



class Emulator(object):
    def __init__(self):
        self.hardware_id = hardware_id
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
        name = prime_key_map.get(key)
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
            ticks = ticks_per_frame
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
############################################################################
# MAIN  (main.py)
############################################################################
# -*- coding: utf-8 -*-
"""
Entry point for the fx-991CN X emulator on the HP Prime.

Run this module on the calculator; it boots the firmware, renders the LCD on
the Prime screen and accepts keyboard input through hpprime.
"""



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
