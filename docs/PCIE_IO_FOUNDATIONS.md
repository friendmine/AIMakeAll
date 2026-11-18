# I/O 与 PCIe：从片内 MMIO 到 Linux 加速设备

物理层可先做[无实板的传输线练习](../labs/01-linear257/README.md)。改变负载、采样相位和衰减，比较接收眼图，再回到本课程的事务、驱动和协议验收。

更新：2026-11-17。IO01–IO06 为本项目原创模块编号，实验全部待实现。路线为 [S0 片内闭环 → S1 PCI/PCIe](ROADMAP.md)，连接 CSAPP 的地址与 I/O、OSTEP 的并发与生命周期、NPU 数值规范及 Linux 驱动。

## 仿真与数字电路路线

遵循 [仿真优先原则](SIMULATION_FIRST.md)。本课程同时交付系统模拟与数字设计：QEMU/EDU/虚拟 NPU 验证 Linux 驱动；独立 TLP 事务模型驱动 BAR、DMA 控制与 NPU 桥 RTL，另做综合检查。初期用共同向量离线对照，不要求购买板卡或先实现 QEMU/RTL 实时联仿。

## 四个边界

IO01 的片内部分进一步接 [MEM-E1/E4](ARCHITECTURE.md) 的事务/仲裁实验，MEM-E2/E3/E5 在独立模型中研究存储调度与 NoC。它们先于或并行于 PCIe 扩展，不意味着已实现 PCIe/AXI 标准控制器；相同请求账本可供 IO06 后续验证复用。

1. 首版 [NPU v0](../specs/npu-v0.md) 仍采用 RV32 裸机、32 位地址、同步轮询；本课程不隐式新增 DMA 引擎、队列、中断或一致性能力。
2. MMIO 是寄存器访问方式，PCIe 是设备互连；PCIe BAR 可以承载 MMIO，两者不是互斥选择。
3. EDU 是 QEMU 的 PCI 教学设备，适合驱动入门；通过 EDU 不代表实现了 PCIe 链路训练、事务层或物理层。
4. Linux 使用独立 guest 与驱动。Ibex 裸机固件不变成 Linux 程序；共享 GEMM 数值规则，设备发现、地址转换和资源管理分别实现。

## 知识与实验

| 模块 | 知识范围 | 原创实验与产物 | 验收门槛 |
| --- | --- | --- | --- |
| IO01 片内互连 | 地址译码、仲裁、握手、背压、AXI/APB 阅读；CPU/NPU/内存连接 | 在 M1/M2 的简单总线上完成合法与非法 MMIO 访问，记录状态转换与波形 | 复位、越界、非法宽度、忙状态和有界等待正确；首版不自称完整 AXI 实现 |
| IO02 PCI 与 PCIe 结构 | 配置空间、BDF、Root Complex/Port、枚举、BAR、能力链；TLP、链路层、PHY 分工 | 在独立 Linux/QEMU 环境枚举 EDU，写最小驱动并读写寄存器 | 记录拓扑/资源，正确绑定、映射、解除绑定和重复装卸；区分 PCI 设备与 PCIe Endpoint |
| IO03 DMA 与地址隔离 | CPU 虚拟/物理地址、DMA 地址、DMA mask、IOMMU、缓存维护和内存屏障 | 驱动经 Linux DMA API 分配/映射缓冲区，复现 EDU 双向传输 | 校验数据与地址位宽，映射/释放配对；未启用 IOMMU 时不宣称已验隔离，隔离故障单独实验 |
| IO04 中断与请求生命周期 | INTx/MSI/MSI-X、确认/屏蔽、竞态、完成通知、取消和复位 | 先用 EDU 的 INTx/MSI，再设计单请求中断与软件有界队列 | 覆盖完成与超时竞态、重复通知、错误恢复；先停止设备访问，再释放缓冲区；MSI-X 另验 |
| IO05 虚拟 PCIe NPU | Endpoint 能力、BAR 寄存器、门铃、缓冲区描述与用户接口 | 新增独立 PCIe 传输规范与虚拟设备，驱动接 C 运行时；先同步单请求，再扩中断/队列 | 保持 INT8 GEMM 数值一致；证明 PCIe 拓扑/能力及 guest 驱动访问；CPU/设备逐元素对照与异常回收通过 |
| IO06 事务级与 RTL 仿真进阶 | TLP 请求/完成子集、BAR/NPU 桥、DMA 控制、批量提交、复位与带宽模型 | 用主机事务模型驱动可综合 RTL；覆盖地址/长度/tag、背压与完成异常，输出波形、网表与成本报告 | RTL/参考逐事务一致、综合无未说明黑盒；周期与参数估算分开；PHY、完整链路及标准合规不计作完成 |

首个驱动实验以 [EDU 官方文档](https://www.qemu.org/docs/master/specs/edu.html) 的寄存器、DMA 限制及 INTx/MSI 能力为准；MSI-X 和更复杂功能不假设 EDU 已支持。

## NPU 传输接口的演进契约

IO06 的寄存器/队列设计复用 [DD](DIGITAL_DESIGN_TIMING.md)，TLP 请求/完成、DMA 边界与复位用 [DV](SYSTEMATIC_VERIFICATION.md) 的需求/参考/性质/故障矩阵验证；事务与周期轨迹按 [SIM](SIMULATION_CREDIBILITY.md) 对齐。只对选定数字接口内的子集形成证据，未建模的信用流控、重放或 PHY 不能据此通过。

保留 v0 的行主序 INT8 × INT8 → INT32、每次命令清零、维度上限和错误语义。PCIe 版本必须单独规定 ABI 版本、寄存器偏移/宽度、DMA 地址位宽、能力发现、状态机和复位后的完成语义；它不是修改一个基地址就能直接复用的裸机驱动。

用户态只提交受校验的形状、缓冲区句柄与范围。内核管理 DMA 映射与生命周期，设备使用 DMA 地址；不得传入宿主指针或假定 guest 物理地址总等于 DMA 地址。[Linux DMA API 指南](https://docs.kernel.org/core-api/dma-api-howto.html)

初版 PCIe NPU 沿用单请求和轮询，明确使用映射后的 DMA 地址访问数据；异步引擎、硬件描述符队列与中断是后续能力。解除绑定和复位时，先阻止新提交并使设备静止，再撤销映射；超时不能直接释放仍被设备访问的内存。非一致性平台另验缓存同步；QEMU 功能通过不能证明真实缓存一致性正确。

## 环境、交付与来源

- IO01 在现有 RV32 规划内开展。IO02–IO04 优先建立独立 Linux/QEMU PCI 教学环境；IO05 再接 RV64 `virt` 的 PCIe 拓扑和 Linux NPU 后端，每个目标组合单独验收。
- 本机 macOS 只作为宿主；Linux 内核模块在 guest 编译/运行。可先用最小 Linux/rootfs 完成课程，LFS 构建独立推进。
- 交付计划：版本清单、拓扑与地址图、驱动与设备源码、独立 ABI、用户示例、正常/故障测试和性能报告。当前未安装依赖、构建驱动或修改 NPU v0。
- 驱动生命周期参考 [Linux PCI 驱动文档](https://docs.kernel.org/PCI/pci.html)，中断参考 [Linux MSI 指南](https://docs.kernel.org/PCI/msi-howto.html)。这些文档为实现参考，实施时锁定内核/QEMU 提交并核对 API。

协议资料可阅读不代表标准全文可重新分发；开源设备模型也不等于真实 PCIe PHY、板卡 IP 和固件全部开源。硬件引入逐项核验来源与许可，虚拟实验不依赖购买板卡。[来源规则](OPEN_SOURCE.md)
