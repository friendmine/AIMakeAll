# QEMU Simulator 主线（待实现）

目标：让 RISC-V guest 使用与 RTL 相同的 MMIO 协议运行 NPU 算子。当前没有 QEMU 补丁或已验证的 guest 启动命令。

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

每条路线固定 QEMU、内核、固件及用户态版本，使用独立配置。功能模拟不证明 PCIe/CXL 链路性能或完整缓存一致性协议正确；本轮没有新增 QEMU 补丁、镜像或运行命令。
