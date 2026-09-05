# CasioEmuNeo

[中文版本](./README.md) | [English](./docs/README_en.md)

卡西欧classwizard系列模拟器，汇编器，调试器，rop自动注入器

## 教程
- [基础界面操作](./docs/intro_ui.md)
- [汇编器使用](./docs/intro_asm.md)
- [rop注入/调试](./docs/intro_rop.md)

## 不想从源码构建？下载windows预编译版本  
[release](https://github.com/qiufuyu123/CasioEmuNeo/releases)

## 构建
0. 安装 xmake & Mingw & 下载字体
   1. `curl -fsSL https://xmake.io/shget.text | bash`   

   2. 安装并配置 Mingw64 *(windows下选则Posix版本!!!不是win32版本)
   3. [字体](http://unifoundry.com/pub/unifont/unifont-15.1.05/font-builds/unifont-15.1.05.otf) 下载,重命名为unifont.otf,放到工程根目录
1. 构建模拟器  
   ```
   cd emulator
   xmake f -p mingw
   xmake
   xmake run CasioEmuX ../models/fx991cnx
   ```  

2. *可选* `反编译器`  
   ```
   cd disas
   make
   ```
3. *可选* 构建机型  
	下载对应机型的 `rom`,命名为 `rom.bin` 放在models 目录下对应名称的目录内  
    **注意:**  
    **由于casio版权问题，源码不包含任何rom,rom文件请自行找资源下载**  
    **如果想要fx991cnx的rom，请到release页面下载编译好的exe版本**
   
   例子, fx991cnx:
   ```
	cd disas
   ```
   ```
   ./bin/u8-disas ../models/fx991cnx/rom.bin  0 0x40000 ./_disas.txt
   ```
   将_disas.txt复制到 models/fxcnx991目录
   ```
   cp ./_disas.txt ../models/fx991cnx/
   ```
   修改 `model.lua`  
   设置`rom_path` 为`"rom.bin"`  

## 近期修复（2026-03）
- 修复 Linux/Arch 下 `xmake` 链接 Lua 版本不匹配导致的 `lua_newuserdata` 链接失败。
- 修复 `fx991cnx` 机型在 UI 启动时读取 `ram_length/ram_start` 导致的异常退出，改为按硬件类型自动推导 RAM 显示区间。
- 修复 `_disas.txt` 解析过程的异常崩溃，增加容错处理，避免 `terminate called without an active exception`。
- 修复 GUI 相关线程生命周期问题（事件循环/监视线程），改善窗口关闭时稳定性。
- 默认配置中的机型路径已改为仓库相对路径（`models/fx991cnx`）。

## 首次启动引导（ROM/机型目录）
- 程序启动时会优先使用命令行传入的 `model` 参数；若未传入则读取 `config.ini` 的 `settings.model`。
- 当 `model.lua` 或 `rom_path` 对应 ROM 文件无效时，会弹出启动引导窗口，提示输入机型目录（例如 `models/fx991cnx`）。
- 引导文案会根据系统语言环境自动切换（中文环境优先显示中文）。
- 引导支持两种目录选择方式：手动文本输入，或通过桌面目录选择器（`zenity`/`kdialog`）浏览选择。
- 引导校验通过后会自动写回 `config.ini`，后续启动将直接使用上次有效目录。
- `_disas.txt` 缺失不再导致程序直接退出，仅反汇编视图不可用。
- 字体加载支持系统字体回退：优先使用 `config.ini` 的 `settings.font`，若不可用则自动尝试常见系统字体（如 Noto CJK/WenQuanYi）。
