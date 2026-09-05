# fx-Prime —— 在HP Prime上使用fx-991 CN X （Work In Progress...）

基于**CasioEmuNeo**基础计算器模拟器，目标机型为**Casio fx-991CN X**（ClassWiz，硬件ID 4）。

所模拟真正的nX-U8 CPU内核、MMU、芯片组/外设逻辑以及LCD渲染。

不使用任何第三方Python库。设备上的所有输入/输出均通过HP Prime的MicroPython解释器中内置的**hpprime**模块完成。

## 文件

    emulator/
      model.py        —— 机型配置（原项目为model.lua）
      cpu.py          —— nX-U8 CPU（解码/分发 + 全部操作码）
      mmu.py          —— 内存管理单元 + 内存映射区域
      chipset.py      —— 芯片组、中断、外设协调
      peripherals.py  —— ROM窗口、电池RAM、屏幕、键盘、
                        待机控制、杂项SFR、定时器
      display.py      —— 通过hpprime进行LCD渲染
      emu.py          —— 模拟器对象 + 主帧循环
      main.py         —— 入口点
      rom.bin         —— 固件镜像（外部资源，未包含于此）
    local_test/       —— 离线设备冒烟测试（使用模拟hpprime）——仅用于测试

## 环境要求

* 一台HP Prime计算器（或HP Prime虚拟计算器），已安装MicroPython。
* 将fx-991CN X ROM 放置于 `emulator/rom.bin`。

启动后，其LCD内容会绘制在Prime屏幕上。按下映射的按键即可驱动模拟键盘。

## 工作原理

### 启动

1. `Emulator.__init__` 构建 `Chipset`，后者创建CPU、MMU和外设。
2. `setup_internals` 将 `rom.bin` 加载到MMU中，并调用每个外设的 `initialise` 方法以注册其内存映射区域。
3. `chipset.reset()` 设置中断表（复位向量）、栈指针，并运行固件的复位处理程序。

### 主循环

`emu.run_once()` 每帧执行以下操作：

1. 运行 `ticks_per_frame` 个机器周期（`chipset.tick()`），每个周期使CPU前进一条指令，并服务外设和中断。
2. 通过 `hpprime` 将LCD帧缓冲区和状态行绘制到Prime屏幕上。
3. 轮询 `hpprime.getkey()`，并将按键按下/释放事件转发给键盘外设。

### CPU

操作码表（源自 `CPU.cpp`）在导入时扩展为一张64K分发表，与C++版的 `SetupOpcodeDispatch` 完全一致。每条指令处理程序均从 `CPUArithmetic/Control/LoadStore/PushPop.cpp` 转录，包括标志位语义（C、Z、S、OV、HC）、DSR前缀、EA自增、异常层级机制以及用于回溯的栈帧。

### 键盘

存在两种模式（与原版一致）：

* `real_hardware = False`（默认）——模拟官方Casio模拟器接口：按下按键会更新 `0x40000+0x8E00` 处的 `keyboard_in_emu`/`keyboard_out_emu` 寄存器，固件会轮询这些寄存器。
* `real_hardware = True` ——模拟物理键盘矩阵，并带有按键冲突消除（`RecalculateGhost`）。

## 调整键位映射

物理fx-991CN X键盘的扫描码是硬件相关的，**不**随本项目提供。它们位于 `model.button_map` 中，以 `(x, y, w, h, code, name)` 元组形式存放。从HP Prime键码到计算器按键名称的映射位于 `model.prime_key_map`。

如果某个按键在您的机器上无响应：

* 打印Prime返回的原始键码：在 `emu.run_once` 的循环内添加 `print(hpprime.getkey())`。
* 在 `model.prime_key_map` 中添加一项，将该键码映射到正确的按键名称。
* 如果所有按键均无响应，请对照实际的fx-991CN X矩阵检查 `model.button_map` 中的扫描码。

## 本地测试（离线）

文件夹 `local_test` 包含一个模拟的 `hpprime` 模块以及一个冒烟测试，可在桌面Python解释器上运行CPU/MMU/外设：

    cd fx991cnx_hp_prime/local_test
    python smoke_test.py

该测试会验证固件能否启动（ROM加载，PC推进）、键盘是否能报告按下的按键，以及ADD/MOV等操作数计算是否正确。

## 性能说明

HP Prime的速度远慢于台式机CPU，因此模拟器**无法**实时运行。`model.ticks_per_frame` 控制每刷新一次屏幕执行多少个机器周期；降低该值可使输入响应更灵敏，提高该值则让计算器每帧做更多工作。请根据实际体验调整。

## 许可协议

移植的逻辑源自CasioEmuNeo (https://github.com/qiufuyu123/CasioEmuNeo)。
Casio固件的版权归Casio Computer Co., Ltd.所有。
