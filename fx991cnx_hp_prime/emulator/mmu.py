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
