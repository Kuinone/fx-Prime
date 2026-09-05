# CasioEmuNeo

[中文版本](../README.md) | [English](./README_en.md)

An emulator and disassembler for the CASIO calculator series using the nX-U8/100 core.  
With debuggers.

## Guide

## Build
0. install xmake  
   `curl -fsSL https://xmake.io/shget.text | bash`   
   install and configure Mingw64
1. notice that this project has already included the full `fx991cn` debugging resources  
   which means you don need to download any extra resources for `fx991cnx`  
   To run debug on it, please:  
   ```
   cd emulator
   xmake f -p mingw
   xmake
   xmake run CasioEmuX ../models/fx991cnx
   ```  
   Other models please follow the instructions below:

2. build `disas`  
   ```
   cd disas
   make
   ```
3. build model directory  
	download `rom` as name `rom.bin`  in your model's directory
   
   for example, fx991cnx:
   ```
	cd disas
   ```
   REMEMBER cd to `disas` IS IMPORTANT!  
   ```
   ./bin/u8-disas ../models/fx991cnx/rom.bin  0 0x40000 ./_disas.txt
   ```
   check _disas.txt and make sure it successfully generated  
   then, copy it to your model's directory
   ```
   cp ./_disas.txt ../models/fx991cnx/
   ```
   then modify `model.lua`  
   set `rom_path` to `"rom.bin"`  

4. build emulator & debugger
   ```
   cd emulator
   xmake
   ``` 
   wait until everything is done  
   then  
	```
	xmake run CasioEmuX ../models/fx991cnx
	```

## First-run startup guide (model/ROM)
- The emulator uses command-line `model` first; if not provided, it falls back to `settings.model` in `config.ini`.
- If the selected model directory is invalid (missing `model.lua` or missing ROM file defined by `rom_path`), a startup guide window is shown.
- Guide text now follows system locale (Chinese locale shows Chinese guide text).
- The guide supports both manual text input and desktop directory picker (`zenity`/`kdialog`) when available.
- After a valid model directory is confirmed, the path is saved to `config.ini` for next launch.
- Missing `_disas.txt` no longer crashes startup; only the disassembly panel is unavailable.
- Font loading supports system fallback: it uses `settings.font` first, then tries common system fonts (e.g. Noto CJK/WenQuanYi) if unavailable.