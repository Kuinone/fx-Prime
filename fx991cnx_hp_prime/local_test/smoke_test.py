# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from emulator import model

class MiniEmu(object):
    def __init__(self):
        self.hardware_id = model.hardware_id
        self.strict_memory = False
        self.pause_on_mem_error = False
        from emulator.chipset import Chipset
        self.chipset = Chipset(self)
        self.chipset.setup()
        self.chipset.setup_internals()
        self.chipset.reset()
    def handle_memory_error(self):
        pass

emu = MiniEmu()
scr = emu.chipset.peripherals[2]
kb = emu.chipset.peripherals[3]
print('rom:', len(emu.chipset.rom_data), 'reset pc=%x sp=%x' % (emu.chipset.cpu.reg_pc, emu.chipset.cpu.reg_sp))

for i in range(3000000):
    emu.chipset.tick()
    if i == 1500000:
        kb.press_button(63)   # power on
    if i == 1700000:
        kb.release_all()
    if i == 1800000:
        kb.press_button(kb.buttons_by_name['MENU'])
    if i == 1900000:
        kb.release_all()

print('after boot: pc=%x csr=%x psw=%x mode=%x contrast=%x' % (emu.chipset.cpu.reg_pc, emu.chipset.cpu.reg_csr, emu.chipset.cpu.reg_epsw[0], scr.screen_mode, scr.screen_contrast))
buf = scr.screen_buffer
nonzero = sum(1 for b in buf if b)
print('screen nonzero bytes:', nonzero, 'of', len(buf))

# CPU opcode test
rom = emu.chipset.rom_data
prog = bytes([0x05,0x00, 0x07,0x01, 0x11,0x80])
for i, v in enumerate(prog):
    rom[i] = v
cpu = emu.chipset.cpu
cpu.reg_csr = 0
cpu.reg_pc = 0
for i in range(3):
    cpu.next()
print('cpu test: r0=%x r1=%x (want r0=c,r1=7)' % (cpu.reg_r[0], cpu.reg_r[1]))

prog2 = bytes([0xff,0x00, 0x01,0x01, 0x11,0x80])
for i, v in enumerate(prog2):
    rom[i] = v
cpu.reg_csr = 0
cpu.reg_pc = 0
for i in range(3):
    cpu.next()
print('carry test: r0=%x psw=%x (want r0=0, C+Z set)' % (cpu.reg_r[0], cpu.reg_epsw[0]))
print('OK test done');
