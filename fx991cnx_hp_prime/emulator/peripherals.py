# -*- coding: utf-8 -*-
"""
Peripheral devices for the fx-991CN X (ClassWiz) emulator.

Ported from the C++ emulator (Peripheral/*.cpp + Chipset/InterruptSource.cpp).
Only the logic needed for a basic calculator is kept: ROM window, battery
backed RAM, screen framebuffer + SFRs, keyboard, standby control,
miscellaneous registers and the timer.  Debug / ROP features are omitted.
"""

from .mmu import Region, mem_region, sfreg_uint, ignore_region
from . import model



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
        real_hardware = model.real_hardware
        if not real_hardware:
            self.ram_size += 0x100

        self.ram_buffer = bytearray(self.ram_size)  # all zero

        mmu = self.chipset.mmu
        mmu.register_region(mem_region(base, self.ram_size, self.ram_buffer))
        if not real_hardware:
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
        self.n_row = model.N_ROW
        self.row_size = model.ROW_SIZE
        self.offset = model.OFFSET
        self.row_size_disp = model.ROW_SIZE_DISP
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
        mmu.register_region(Region(model.screen_base, self.screen_size, rread, rwrite))

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
        if not model.real_hardware:
            self.keyboard_ready_emu = 0
            self.keyboard_out_emu = 0
            self.keyboard_in_emu = 0
            self.keyboard_pd_emu = model.pd_value
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
        for (x, y, w, h, code, name) in model.button_map:
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
        if not model.real_hardware:
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
            if model.real_hardware:
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
            if model.real_hardware:
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
        self.real_hardware = model.real_hardware
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
        cps = model.cycles_per_second
        self.ext_to_int_next = cps * (self.ext_to_int_int_done + 1) // self.ext_to_int_frequency
        if self.data_control & 0x01:
            if self.data_counter == (1 if self.timer_skipped else self.data_interval):
                self.data_counter = 0
                if self.interrupt_source.enabled():
                    self.raise_required = True
            self.data_counter += 1