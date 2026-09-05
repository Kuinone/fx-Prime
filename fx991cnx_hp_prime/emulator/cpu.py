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
        dispatch = [-1] * 0x10000
        sources = OPCODE_SOURCES
        for sidx, src in enumerate(sources):
            _func, hint, opcode, operands = src
            varying_bits = 0
            for _size, mask, shift in operands:
                varying_bits |= mask << shift
            permutation = [0] * 0x10000
            count = 1
            permutation[0] = opcode
            checkbit = 0x8000
            while checkbit:
                if varying_bits & checkbit:
                    for px in range(count):
                        permutation[px + count] = permutation[px] | checkbit
                    count <<= 1
                checkbit >>= 1
            for px in range(count):
                idx = permutation[px]
                if dispatch[idx] == -1:
                    dispatch[idx] = sidx
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
            if sidx == -1:
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
