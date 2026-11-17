# 系统架构与技术选择

总体学习依赖见 [全景规划图](PROJECT_MAP.md)。CSAPP 的信息表示、处理器、存储、链接、异常、I/O 与并发组成跨层基础，详细映射见 [CSAPP 模块](CSAPP_FOUNDATIONS.md)。书中的 x86-64/Y86-64 教学示例与本项目 RISC-V 目标分别维护，不共享未经适配的二进制与 ABI 假设。

## 端到端数据流

模型与学习方法由 [Understanding Deep Learning 基础](UDL_FOUNDATIONS.md) 支撑，连接损失、梯度、Transformer 与质量评估。训练保留在宿主机，首版 NPU 加速推理线性层；量化和设备接入是本项目独立的工程实验。

### 模型转换与运行时边界

[AI 编译路线](AI_COMPILATION.md) 增加有限计算图检查 → 布局/量化 → GEMM 分块 → 缓冲区规划 → 执行计划。编译器决定静态计划，运行时绑定内存并处理动态输入，驱动执行设备协议。首版采用小型自写转换器，MLIR 为后续进阶；尚未实现通用模型导出。

[算法](ALGORITHMS_FOUNDATIONS.md) 支撑图排序、索引和调度；[OSTEP](OSTEP_FOUNDATIONS.md) 支撑内存生命周期、同步和持久状态。所有新连接层目前属于设计。计划必须遵守 NPU v0 每次清零、最大维度 256、32 位地址与同步轮询等约束；K 分块部分和由运行时合并，CPU 承担 scale/bias 和其他回退。

[工程专项](ENGINEERING_BRIDGES.md) 统一数值、数据、性能和检索验收。性能模型、硬件仿真周期和宿主墙钟时间分开记录，不用理论峰值代替实测。

### 推理时的数据流

```mermaid
flowchart TD
    A[用户任务] --> B[Agent 循环与工具校验]
    B --> C[自训练小型 LLM]
    C --> D[推理运行时与算子分派]
    D --> E[CPU: 归一化 / Softmax / 控制]
    D --> F[INT8 GEMM 接口]
    F --> G[Python / C 参考后端]
    F --> H[RISC-V guest 驱动]
    H --> I[MMIO 设备 ABI]
    I --> J[QEMU 功能设备模型]
    I --> K[RTL: RISC-V SoC + NPU]
```

这是目标架构，目前只有 Python GEMM 和独立 MAC RTL 实验落地。QEMU 与 RTL 是两种执行环境，共享算子语义和驱动协议；QEMU 不会自动执行 Verilog，也不会自动拥有自定义 NPU。

已有独立芯片实验环境现已作为项目的外部基础设施登记，详见 [本地 EDA 依赖与接入分析](LOCAL_EDA_ENVIRONMENT.md)。这些工具和历史案例尚未组成 AIMakeAll 的 SoC；两套 PDK、不同仿真器版本及 SRAM 交付物必须分别管理。

## 首版选择

全项目遵循 [仿真优先原则](SIMULATION_FIRST.md)：数字模块以参考模型 → RTL 仿真 → 逻辑综合交付，物理设计可选；QEMU/Linux 验证驱动和应用。网络、PCIe、CXL 分别配置协议/事务模型，PHY 与实板不是核心依赖。QEMU 功能模型、可综合 RTL、测试台和完整标准合规须分别标明。

| 层 | 默认路线 | 原因与边界 |
| --- | --- | --- |
| RISC-V CPU | Ibex RV32IMC，裸机 | CPU 已开源；教学重点放在系统集成。不是 Linux 平台 |
| 教学 NPU | 自实现 SystemVerilog INT8 MAC → 4×4 阵列 | 算术、数据流和带宽可逐层解释 |
| 硬件验证 | Verilator；后续增加 Yosys 综合 | 软件仿真无需购买板卡；器件适配另做评估 |
| 软件模拟 | QEMU RISC-V 系统模拟 + 自定义 MMIO 设备 | 固定板级映射，尽量复用裸机驱动 |
| 模型训练 | 自写模型结构，PyTorch 自动求导，CPU 起步 | 不需要闭源服务；GPU 加速是可选项 |
| 部署 | C 标量后端 → guest NPU 后端 | 先保证数值一致，再优化 |
| Agent | 简单显式状态机 + JSON 工具协议 | 避免框架掩盖模型、工具与运行时之间的边界 |

Ibex 是面向嵌入式控制的开源 32 位 RISC-V 核，见 [上游项目](https://github.com/lowRISC/ibex)。未来如需 Linux，需另选具有合适特权级、MMU 等支持的 CPU/SoC，并单独维护 RV64 配置。

Gemmini 作为后续对照学习材料：它属于 Chipyard/Chisel 生态，其集成方式和指令接口与本项目 MMIO 路线不同，不能直接当作 Ibex 外设插入。见 [Gemmini 上游](https://github.com/ucb-bar/gemmini)。

## Linux 系统构建扩展

[Linux From Scratch](LFS_FOUNDATIONS.md) 补充工具链自举、用户态、内核与启动知识。基础复现采用独立 Linux x86-64 环境；RV64 Linux/QEMU 为后续适配线，单独配置固件、设备树、内核、rootfs 和 Linux NPU 驱动。初期裸机固件与 Linux 用户进程分别构建，共享数值规范，不共享未经适配的二进制和设备访问代码。

Linux 路线中由内核驱动管理设备资源与缓冲区，用户态 C 运行时通过明确接口提交计算。模型训练留在宿主环境；guest 的推理与工具服务独立验收启动、权限、日志、停止和重启。目前尚无 LFS 镜像或 Linux 驱动实现。

## 互连、通信与内存扩展

新增 [网络](NETWORKING_FOUNDATIONS.md)、[I/O 与 PCIe](PCIE_IO_FOUNDATIONS.md)、[CXL](CXL_MEMORY_FOUNDATIONS.md) 三条课程，全部待实现。互连负责连接不同层次，不能把三者视为线性的接口替换。

```mermaid
flowchart LR
    AG[远程 Agent 客户端] -->|网络 RPC| SVC[Linux 推理服务]
    SVC --> RUN[运行时与 CPU 后端]
    RUN -->|驱动提交| PCI[PCIe NPU 扩展]
    RUN -->|内存分配与放置| MEM[本地内存 / CXL Type 3 扩展]
    BARE[RV32 裸机 CPU] -->|片内 MMIO| NPU[首版教学 NPU]
```

上图为目标连接关系，CXL 与 PCIe NPU 尚未集成在同一验证平台。首个 CXL 实验用独立 x86-64 q35 guest，RV64 迁移另验；不直接扩大首版裸机 NPU 的能力。

- **设备路径**：保留 GEMM 数值语义，新增独立 PCIe 传输 ABI。Linux 驱动管理 BAR、DMA 映射、中断与资源生命周期，用户态提交缓冲区句柄；不复用裸机地址假设。
- **网络路径**：协议传输经过校验的输入与结果，不传可解引用地址。先 CPU 服务，再接真实 NPU 后端；超时、取消、重试及背压贯穿 Agent 与服务端。
- **内存路径**：CXL 初期解决可访问容量与放置问题。NPU v0 只有 32 位地址，访问扩展内存需额外证明映射能力或使用暂存搬运；编译器的放置提示由运行时兑现。

按 [S0–S3](ROADMAP.md) 分阶段验收，网络可并行。QEMU 的功能结果、网络服务墙钟、参数化带宽/延迟估算、真实 PCIe/CXL/RDMA 性能分别报告。

## QEMU 的职责

新增的 [DD](DIGITAL_DESIGN_TIMING.md)、[DV](SYSTEMATIC_VERIFICATION.md)、[SIM](SIMULATION_CREDIBILITY.md) 在接口边界协同：DD 定义采样/复位/握手，DV 按需求验证实现，SIM 规定时间推进、事件顺序与模型适用性。功能参考只比较承诺的事务结果，周期模型与 RTL 才在共同采样规则下比较周期；QEMU/RTL 首先做离线对照。共享 FIFO 为独立教学实验，不更改现有 MAC 复位或 NPU v0 协议。

QEMU 支持 32/64 位 RISC-V 系统模拟，但机器模型决定设备与内存映射；`virt` 并非某个真实硬件 SoC 的复制品。见 [QEMU 官方说明](https://www.qemu.org/docs/master/system/target-riscv.html)。

本项目计划先建立可运行软件的虚拟平台，不宣称它精确复现 Ibex 的流水线、缓存或周期。裸机代码的 ISA、链接地址、UART 和 NPU 地址必须与所选机器一致。Linux + RV64 `virt` 属于后续扩展，不能复用 RV32 裸机映像直接启动。

## 如何证明加速

同一模型、同一输入、同一量化精度下分别测量：

1. 宿主机原生 CPU 推理：作为现实使用基线。
2. QEMU guest 的 CPU 标量推理：衡量模拟环境内的软件路径。
3. QEMU guest + NPU 设备后端：衡量设备卸载与宿主机实现带来的变化。
4. RTL/未来 FPGA：记录真实周期或板卡耗时；RTL 仿真的墙钟速度不等于硬件速度。

每项记录预热次数、重复次数、输入形状、线程数、构建选项、中位数与 P95。模型推理分别记录 prefill tokens/s、decode tokens/s、峰值内存与搬运字节数。Agent 另报总任务耗时和任务成功率。

矩阵核心快不等于整个模型快。例如可加速部分占总耗时 70%、该部分快 10 倍时，理想总加速比仅为 `1 / (0.30 + 0.70 / 10) ≈ 2.70`，且还没计入额外搬运开销。

## 内存与模型规模

首版 RV32 采用小模型和短上下文。实际 SRAM/RAM 容量在 SoC 集成前确定，权重、激活、KV cache 与代码必须有显式预算。训练不在教学 NPU 上执行；第一阶段 NPU 仅承担推理的整数矩阵乘法。扩展训练算子需要新的精度、梯度和存储设计。

## 领域 04 深化：体系结构与存储系统实验

以下 ARCH-E1–E6 是既有领域 04 内的原创实验编号，连接领域 05/08/11/14/15，不新增一级知识领域或独立必修主线。全部待实现；先做软件/周期模型，再按需求映射到 RTL，不依赖板卡。方法复用 DD/DV/SIM 与 ENG03。

| 子实验 | 知识与前置 | 实验产物 | 验收要求 |
| --- | --- | --- | --- |
| ARCH-E1 数据流与复用 | GEMM、AL01、AC07；循环次序、分块、权重/输入/部分和驻留 | 固定小矩阵，比较朴素与至少两种分块/数据流，输出访问轨迹和每层读写字节账本 | 结果逐元素一致；区分真实访问与模型估算，计入尾块、打包与部分和；不假设 v0 支持旧 C 累加 |
| ARCH-E2 局部存储与 bank | DD03/DD08；端口数、bank 映射、冲突、仲裁、容量预算 | 在相同阵列/数据流下扫描局部存储容量与 bank 数，先周期模型后可选 RTL | 明确每 bank 端口和周期能力；冲突时停顿而非丢数据；报告周期、利用率和容量，不只比较 MAC 数量 |
| ARCH-E3 Cache 与 scratchpad | CS06、OS03/OS04；行/组/替换/写策略、TLB 与 Cache 区别 | 地址轨迹驱动的小 Cache 模拟器，对比显式分块局部存储；增加 stride/工作集用例 | 手算轨迹可核对 hit/miss/写回；声明冷启动与策略；缓存行不是页，CPU Cache 不是模型 KV Cache |
| ARCH-E4 共享内存与可见性 | OS05/OS07、IO03；内存顺序、原子性、缓存维护、DMA 地址与屏障 | 教学模型模拟 CPU 缓存和设备访问，制造旧输入/旧输出；另在具备条件的 Linux guest 验证 DMA API 路径 | 区分 cache coherence、内存顺序与软件同步；屏障不自动清理非一致缓存，volatile 不代替同步；未建模/未跑平台单列 |
| ARCH-E5 一致性状态模型 | ARCH-E3/E4、DV03/DV05；MSI 状态、失效确认、权限与数据版本 | 两个缓存与目录的有限状态模型，枚举读写/失效/确认交错，再注入确认丢失 | 检查单写者/多读者、最新值与无非法权限；活性需公平性/响应假设；MSI 教学通过不代表 CXL 合规或已实现多核 |
| ARCH-E6 设计空间与存储分层 | SIM05–SIM07、ENG03；算术强度、带宽/计算上界、容量与放置 | 固定精度/负载，扫描阵列规模、bank/缓冲区、带宽/延迟；后续接权重/KV 的 NUMA/CXL 放置 | 参数有来源，留出校验用例；理论上界与实测/仿真分栏，计入打包/搬运/回退；单次结果不推成普遍最优 |

首组先做 ARCH-E1：固定原始输入、数值语义与有效工作量，只改变循环/分块。记录主存↔局部存储↔阵列各边界的字节与访问次数；计数规则明确读写、重读、padding 是否计入。ARCH-E2 再在同一负载下改变存储约束，避免同时改变模型、量化或硬件规模导致比较失真。

ARCH-E3–E5 为独立模拟练习，不把 Cache、原子指令、多核或一致性支持隐含加入 Ibex/NPU v0。首版仍按无 coherence 保证、同步轮询及 32 位设备地址推进。ARCH-E6 的重叠收益仅在模型/实现确有双缓冲和异步机制时评估；缓存/一致性模型不是首个 G2 闭环的前置条件。

理论范围参考 [MIT 6.823 体系结构课程](https://ocw.mit.edu/courses/6-823-computer-system-architecture-fall-2005/pages/syllabus/)，MSI 模型参考 [gem5 教程](https://www.gem5.org/documentation/learning_gem5/part3/cache-intro/)，Linux DMA 边界参考 [内核指南](https://docs.kernel.org/core-api/dma-api-howto.html)。仅组织原创实验与来源，不复制整套课程或引入大型模拟器为必需依赖。
