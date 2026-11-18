# 在 QEMU 的 RV32 virt 上运行本地教学 NPU

此目录针对 QEMU 9.2.4 的教学构建。补丁在 virt 的空闲地址 0x10010000 映射 4 KiB MMIO，设备按 v0 协议校验 guest RAM 并计算有符号 INT8 乘加。guest 的轮询、内存屏障、两次提交和结果合并在模拟的 RISC-V CPU 上执行。单 MAC RTL 在 Verilator 中单独运行。[设备契约](../../specs/npu-v0.md) · [学生实验](../../labs/01-linear257/README.md)

从仓库根目录执行。构建需要 C/C++ 工具链、Python、Meson、Ninja、pkg-config、GLib、libfdt、patch 和 tar/xz。macOS 使用 Homebrew dtc（可设 DTC_PREFIX），Linux 使用开发头文件与库。guest 需要能生成 RV32IM/ILP32 的裸机 GCC，可通过 RISCV_CC 指定。源码和二进制位于 build/，不执行系统安装。首轮建议预留 2 GiB 磁盘，默认最多 4 个编译任务，可设 JOBS。下载耗时与编译成本单列。

```sh
mkdir -p build/downloads
curl -fL https://download.qemu.org/qemu-9.2.4.tar.xz -o build/downloads/qemu-9.2.4.tar.xz
sh simulator/qemu-v0/build.sh build/downloads/qemu-9.2.4.tar.xz
make device-test design-trial
```

脚本先核对锁定的压缩包 SHA-256，再展开源码、打补丁并只构建 riscv32-softmmu。自定义构建目录时将二进制传给 make，例如 `make design-trial LINEAR_QEMU=/absolute/path/to/qemu-system-riscv32`。普通发行版 QEMU 的 virt 机器没有这里新增的窗口。[QEMU 官方发布目录](https://download.qemu.org/)

| 验证入口 | 覆盖的行为 |
| --- | --- |
| `make device-test` | qtest 直接访问寄存器和 RAM，以虚拟时钟推进单个命令。覆盖非法命令、形状、地址/对齐、输出重叠，错误后输出保护，无效宽度、非对齐写与只读写入无副作用，BUSY 时配置/CLEAR 无效、DONE 后 CLEAR，以及忙时复位取消和清零 |
| `make linear-all` | 编译裸机 ELF，从 0x80000000 启动，以 UART 输出全部部分和及最终分子，以 SiFive test 窗口返回通过/失败。主机逐元素核对独立参考，记录输入哈希 |
| `make design-trial` | 在两种预算下分别运行四条算术路径，并重放工具助手的引用纠错任务 |

教学机器为单核、32 MiB RAM，设备窗口由裸机板级合同给出。IO 限小端对齐的 32 位访问。输入和输出必须完整落在 32 位可表示的 guest RAM，输出与两个输入均不得重叠。延后 1000 虚拟纳秒完成事务，供测试观察 BUSY 与取消。该常量只规定模型事件顺序。当前实验范围为一次性启动的裸机进程，迁移、快照、热插拔、Linux 枚举与完整 RTL 控制器留待后续验收。

设备源、头文件及 QEMU 集成补丁采用 GPL-2.0-or-later，许可文本见 [COPYING](COPYING)。仓库内的数值、客体及教材使用项目许可。压缩包与构建产物保留各自的上游文件级许可。
