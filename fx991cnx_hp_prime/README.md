# fx-991CN X (Casio ClassWiz) emulator for HP Prime

A self-contained MicroPython port of the **CasioEmuNeo** basic calculator
emulator, targeting the **Casio fx-991CN X** (ClassWiz, hardware id 4).

Everything unrelated to a plain calculator has been stripped out: the debugger,
the ROP injection tools, the disassembler view, the Lua scripting hooks and the
GUI.  What remains is the real nX-U8 CPU core, the MMU, the chipset/peripheral
logic and the LCD rendering — i.e. a working, basic calculator.

No third-party Python library is used.  All input/output on the device goes
through the built-in **hpprime** module of the HP Prime's MicroPython interpreter.

## Files

    emulator/
      model.py        model configuration (was model.lua in the original)
      cpu.py          nX-U8 CPU (decode/dispatch + all opcodes)
      mmu.py          memory management unit + memory-mapped regions
      chipset.py      chipset, interrupts, peripheral orchestration
      peripherals.py  ROM window, battery RAM, screen, keyboard,
                      standby control, miscellaneous SFRs, timer
      display.py      LCD rendering through hpprime
      emu.py          emulator object + main frame loop
      main.py         entry point
      rom.bin         the firmware image (external resource, not included here)
    local_test/       off-device smoke test (uses a mock hpprime) - testing only

## Requirements

* An HP Prime calculator (or the HP Prime Virtual Calculator) with MicroPython
  firmware installed.
* The fx-991CN X firmware image placed at `emulator/rom.bin`.
  (Casio firmware is copyrighted; obtain your own copy. The original project
  does not ship a ROM.)

## Installing on the HP Prime

1. Copy the whole `emulator` folder plus the firmware image
   `rom.bin` into the calculator's flash (e.g. into the `HOME` directory
   or the Py script folder).
2. In the HP Prime MicroPython app, run the `main.py` module:
   `run("main.py")` or `run("emulator/main.py")` depending on where you put
   the files.

The calculator firmware boots and its LCD is drawn on the Prime's screen.
Pressing the mapped keys drives the emulated keyboard.

## How it works

### Boot

1. `Emulator.__init__` builds the `Chipset`, which creates the CPU, MMU and
   peripherals.
2. `setup_internals` loads `rom.bin` into the MMU and calls each
   peripheral's `initialise` to register its memory-mapped regions.
3. `chipset.reset()` sets the interrupt table (reset vector), stack pointer
   and runs the firmware's reset handler.

### Main loop

`emu.run_once()` does, per frame:

1. Runs `ticks_per_frame` machine cycles (`chipset.tick()`), each of which
   advances the CPU by one instruction and services the peripherals and
   interrupts.
2. Paints the LCD framebuffer and status row to the Prime screen through
   `hpprime`.
3. Polls `hpprime.getkey()` and forwards key press/release to the keyboard
   peripheral.

### CPU

The opcode table (from `CPU.cpp`) is expanded at import time into a 64K
dispatch table, exactly like the C++ `SetupOpcodeDispatch`.  Each instruction
handler was transcribed from `CPUArithmetic/Control/LoadStore/PushPop.cpp`
including flag semantics (C, Z, S, OV, HC), DSR prefixes, EA bumping, the
exception-level machinery and the stack frames used for backtraces.

### Keyboard

Two modes exist (mirroring the original):

* `real_hardware = False` (default) - emulates the official Casio emulator
  interface: pressing a key updates the `keyboard_in_emu`/`keyboard_out_emu`
  registers at `0x40000+0x8E00`, which the firmware polls.
* `real_hardware = True` - emulates the physical key matrix with ghost-key
  elimination (`RecalculateGhost`).

## Tuning the key map

The scan codes of a physical fx-991CN X keyboard are hardware-specific and are
**not** shipped with this project)Skip.  They live in `model.button_map` as
`(x, y, w, h, code, name)` tuples.  The mapping from HP Prime key codes to
calculator button names lives in `model.prime_key_map`.

If a key does not respond on your machine:

* Print the raw key code the Prime returns: add
  `print(hpprime.getkey())` inside the loop of `emu.run_once`.
* Add an entry to `model.prime_key_map` mapping that code to the correct
  button name.
* If no buttons respond at all, check `model.button_map` scan codes against
  the actual fx-991CN X matrix.

## Local testing (off-device)

The folder `local_test` contains a mock `hpprime` module and a smoke test
that runs the CPU/MMU/peripherals on a desktop Python interpreter:

    cd fx991cnx_hp_prime/local_test
    python smoke_test.py

It verifies that the firmware boots (ROM loads, PC advances), that the
keyboard reports a pressed key, and that ADD/MOV opcodes compute correctly.

## Performance notes

The HP Prime is far slower than a desktop CPU, so the emulator does **not** run
in real time.  `model.ticks_per_frame` controls how many machine cycles are
executed per screen refresh; lowering it makes input more responsive, raising
it makes the calculator do more work per frame.  Adjust it to taste.

## License

The ported logic is derived from CasioEmuNeo (https://github.com/qiufuyu123/CasioEmuNeo).
The Casio firmware remains the property of Casio Computer Co., Ltd.
