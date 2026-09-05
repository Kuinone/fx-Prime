# -*- coding: utf-8 -*-
"""
Chipset: owns the CPU, MMU, ROM image and the peripheral set, and manages
interrupts / run state.

Ported from the C++ emulator (Chipset/Chipset.cpp, Chipset/InterruptSource.cpp).
Debug / ROP / Lua hooking code has been removed.
"""

from .mmu import MMU, Region, mem_region, sfreg_uint, ignore_region
from .cpu import CPU, MM_LARGE
from . import model
from . import peripherals

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
        self.cpu.impl_csr_mask = model.csr_mask

    # ------------------------------------------------------------------
    def setup(self):
        self.cpu.set_memory_model(MM_LARGE)
        self.construct_peripherals()

    # model module constants: import CPU.MM_LARGE as MM_LARGE
    # We re-import below to keep module import order sane.

    def construct_peripherals(self):
        hwid = self.emulator.hardware_id
        self.peripherals.append(peripherals.ROMWindow(self))
        self.peripherals.append(peripherals.BatteryBackedRAM(self))
        self.peripherals.append(peripherals.Screen(self))
        self.peripherals.append(peripherals.Keyboard(self))
        self.peripherals.append(peripherals.StandbyControl(self))
        self.peripherals.append(peripherals.Miscellaneous(self))
        self.peripherals.append(peripherals.Timer(self))

    def setup_internals(self):
        # load the ROM image from the external resource file
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, model.rom_path)
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