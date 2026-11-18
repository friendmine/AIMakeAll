# QEMU Simulator 主线

目标：让 RISC-V guest 使用与 RTL 相同的 MMIO 协议运行 NPU 算子。实验 03 已用同一份 RV32 固件在 QEMU 功能设备及 PicoRV32 RTL 上验证前馈投影与完整符号生成。[实验 03](../labs/03-rv32-generation/README.md) 按[固定版本的 QEMU 构建与设备检查](qemu-v0/README.md)构建，再用[实验 01](../labs/01-linear257/README.md)比较与单 MAC 的算术结果。

遵循 [仿真优先原则](../docs/SIMULATION_FIRST.md)。QEMU 验证系统软件，Verilator 验证数字 RTL，协议模型提供主机/网口/内存事务；初期通过相同输入与轨迹离线对照。实时联合仿真的时钟、事件、内存与复位桥接是独立后续实现，不作为首个闭环前提。

模型方法参考 [SIM01–SIM08](../docs/SIMULATION_CREDIBILITY.md)，验证参考 [DV01–DV08](../docs/SYSTEMATIC_VERIFICATION.md)：先记录抽象层次、接口假设、时间/事件和复位 epoch，保存可重放输入，再与独立参考/RTL 对照。周期模型与 QEMU 功能模型各报适用范围；未经实测校准的参数不作为硬件性能事实。

实施顺序：

1. 选择并锁定 QEMU 提交，确认 RV32 裸机机器的 RAM、UART、入口与 CPU 扩展。
2. 建立专用机器或可审查的板级补丁，预留不冲突的设备窗口。
3. 实现寄存器回调、guest 物理内存读写和完整范围校验。
4. 添加独立设备测试，再运行 guest C 程序完成 GEMM。
5. 实现可选宿主机优化后端，保持与参考路径一致的整数溢出语义。

必须覆盖复位、非法宽度、越界 DMA、形状错误、缓冲区重叠和状态机。参考 [ABI 草案](../specs/npu-v0.md)。若采用同步设备回调，须明确 guest 无法观察中间 BUSY 状态的限制；后续异步行为需增加时序与复位测试。

QEMU 内部设备代码沿用对应上游文件的许可要求，不直接套用根目录 MIT 许可。功能设备不是周期精确模型，性能报告遵循 [架构文档](../docs/ARCHITECTURE.md)。

## Linux 系统扩展

新增 [LFS 与 RV64 Linux 路线](../docs/LFS_FOUNDATIONS.md)：先在独立 Linux 环境学习系统构建，再建立 RV64 `virt` 的固件、内核和 rootfs，最后接 NPU 设备描述与 Linux 驱动。极小 initramfs 启动检查与完整 LFS 系统分别验收；RV64 Linux 不替代首版 RV32 裸机实验。目前尚未构建镜像或验证启动。

## 互连与通信扩展（待实现）

- [S1 / IO02–IO05](../docs/PCIE_IO_FOUNDATIONS.md)：Linux/EDU 的 PCI 驱动入门 → 独立虚拟 PCIe NPU。EDU 并不覆盖完整 PCIe 链路，设备数值语义可共用，传输 ABI 与驱动单独实现。
- [S2 / NET01–NET05](../docs/NETWORKING_FOUNDATIONS.md)：回环协议 → 双 guest CPU 服务 → 远程模型/Agent；后端类型和网络配置需可追溯，不要求先完成 NPU。
- [S3 / CX01–CX05](../docs/CXL_MEMORY_FOUNDATIONS.md)：独立 x86-64 q35 + Type 3 内存实验，记录拓扑、译码与实际可访问区域；不假定 RV64 平台自动具备 CXL。

每条路线固定 QEMU、内核、固件及用户态版本，使用独立配置。功能模拟不证明 PCIe/CXL 链路性能或完整缓存一致性协议正确；这些扩展的独立实现与验收仍待推进。
