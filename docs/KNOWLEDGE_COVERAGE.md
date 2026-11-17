# AIMakeAll 知识覆盖范围

更新：2026-11-17。V4 的十八个领域保持不变；本轮在既有领域内补深体系结构与存储系统、数学基础、软件正确性与可复现工程、持久状态与安全，共 24 个子实验，详见下方映射。此前 DD/DV/SIM 的 24 个模块继续以同步 FIFO 为共同起点。覆盖表示已纳入学习规划，尚不代表实验完成。

![AIMakeAll 知识覆盖图 V4：十八个领域，新增数字设计、系统验证与仿真可信度](images/knowledge-coverage-v4.png)

## 十八个领域及阅读入口

V4 表示知识范围；交付方式统一按 [仿真优先原则](SIMULATION_FIRST.md)：数字电路设计与综合、协议/RTL 仿真、QEMU 系统模拟。实板与流片不作为核心要求；新增教学数字子模块不等于完整 PCIe/CXL 标准实现。

| 图中编号 | 领域 | 主要学习内容 | 文档入口 |
| --- | --- | --- | --- |
| 01 | 数学与数值 | 离散与证明、线性代数、微分、优化、概率信息量、数值与统计 | [UDL / MATH-E1–E6](UDL_FOUNDATIONS.md)、[ENG01](ENGINEERING_BRIDGES.md) |
| 02 | 算法与数据结构 | 复杂度、容器、排序、图、动态规划与索引 | [AL01–AL10](ALGORITHMS_FOUNDATIONS.md) |
| 03 | 编程与程序执行 | C、汇编、ABI、链接、内存与整数语义、所有权、调试和复现 | [CSAPP](CSAPP_FOUNDATIONS.md)、[SW-E1–E6](SYSTEMATIC_VERIFICATION.md) |
| 04 | 体系结构与加速器 | RISC-V/NPU、数据流、bank、Cache/scratchpad、可见性与一致性模型 | [硬件](../hardware/README.md)、[ARCH-E1–E6](ARCHITECTURE.md) |
| 05 | 操作系统原理 | 调度、虚拟内存、同步、文件系统、事务恢复与权限 | [OS01–OS12](OSTEP_FOUNDATIONS.md)、[状态实验](ENGINEERING_BRIDGES.md) |
| 06 | Linux 系统构建 | 工具链、用户态、内核、rootfs、启动和服务 | [LFS](LFS_FOUNDATIONS.md) |
| 07 | 模拟器与驱动 | QEMU、虚拟设备、MMIO、中断和 DMA | [模拟器](../simulator/README.md)、[NPU 规范](../specs/npu-v0.md) |
| 08 | AI 编译 | 计算图、IR、布局/量化、分块、内存及执行计划 | [AC01–AC12](AI_COMPILATION.md) |
| 09 | 深度学习基础 | 模型表达、损失、梯度、优化与泛化 | [UDL](UDL_FOUNDATIONS.md) |
| 10 | 从零 LLM | 数据、分词、GPT 逐层实现、预训练、分类/指令微调 | [模型 / LLMs From Scratch 七章映射](../models/README.md)、[MiniMind](MINIMIND_INTEGRATION.md)、[ENG02](ENGINEERING_BRIDGES.md) |
| 11 | 推理运行时 | 计划执行、输入校验、所有权、KV/存储预算与设备调用 | [运行时](../runtime/README.md)、[AI 编译](AI_COMPILATION.md) |
| 12 | Agent 与检索 | 索引、工具权限、持久状态、幂等/未知结果、恢复与审计 | [Agent](../agents/README.md)、[STATE-E1–E6](ENGINEERING_BRIDGES.md) |
| 13 | 网络与分布式通信 | Ethernet/TCP/IP、Socket/RPC、背压与重试、RDMA 进阶 | [NET01–NET06](NETWORKING_FOUNDATIONS.md) |
| 14 | I/O 与 PCIe | 片内互连、枚举/BAR、DMA/IOMMU、中断与 Linux 驱动 | [IO01–IO06](PCIE_IO_FOUNDATIONS.md) |
| 15 | CXL 与异构内存 | 协议与一致性、Type 3、地址译码、NUMA 与模型内存放置 | [CX01–CX06](CXL_MEMORY_FOUNDATIONS.md) |
| 16 | 数字设计与时序 | HDL 语义、流水线/握手、FIFO、复位/CDC、综合与时序约束 | [DD01–DD08](DIGITAL_DESIGN_TIMING.md) |
| 17 | 系统化验证 | 需求追溯、参考/断言、形式/等价、程序检测、故障/模糊测试与复现 | [DV01–DV08 / SW-E1–E6](SYSTEMATIC_VERIFICATION.md) |
| 18 | 仿真建模与可信度 | 模型边界、事件调度、周期/事务、重放、校验/校准与敏感性 | [SIM01–SIM08](SIMULATION_CREDIBILITY.md) |

图中中断、DMA、Linux 驱动等表示课程范围；当前 NPU v0 首版仍为同步轮询，不据图示扩大设备能力。CSAPP、OSTEP、LFS 分别侧重程序视角、系统机制和系统构建。

网络连接节点，PCIe 连接主机与设备，CXL 连接扩展内存并引入一致性相关机制。新增模块按 [S0–S3 阶段](ROADMAP.md) 推进：S0 MMIO 闭环 → S1 PCI/PCIe → S3 CXL；S2 网络可先用 CPU 服务并行，远程 NPU 接入另需本地后端验收。

## 四组深化内容如何归入现有体系

| 深化内容 | 主要归属与实验入口 | 新增的验收证据 |
| --- | --- | --- |
| 体系结构与存储系统 | 04 → 05/08/11/14/15；[ARCH-E1–E6](ARCHITECTURE.md) | 访问/容量账本、周期与冲突、缓存轨迹、可见性反例、有限状态性质、设计空间报告 |
| 数学基础 | 01 → 02/09/16/18；[MATH-E1–E6](UDL_FOUNDATIONS.md) | 推导与反例、残差/梯度对照、条件数与收敛、概率指标、误差与统计波动 |
| 软件正确性与可复现工程 | 03/17 → 06/08/11/18；[SW-E1–E6](SYSTEMATIC_VERIFICATION.md) | C 数值语义、坏包拒绝、检测语料、资源回收、环境 manifest、跨层回归 |
| 持久状态与安全 | 05/12/13；[STATE-E1–E6](ENGINEERING_BRIDGES.md) | 权限边界、任务状态、崩溃恢复、未知结果处理、攻击/资源限制用例、脱敏审计 |

以上为四组各六项的待实现子实验。它们深化已有领域，不增加图中一级编号或仓库一级目录；详细实施顺序见 [整体规划](PROJECT_MAP.md) 和 [里程碑](ROADMAP.md)。领域覆盖图继续使用 V4，新增深度由本页文字索引表达。

## 方法课程与四个工程专项

DD/DV/SIM 是贯穿各领域的方法课程，按 [G0–G3 门槛](ROADMAP.md) 组织：契约 → 同步 FIFO → 单 Linear → 系统扩展。领域 04 关注计算体系结构与 NPU，领域 16 负责可复用数字设计基本功；领域 07 关注 QEMU/驱动，领域 18 负责模型适用性与结论可信度。两两连接，不重复计算实现进度。

[ENG01–ENG04](ENGINEERING_BRIDGES.md) 覆盖数值量化、数据训练、性能与系统验证、检索与 Agent 可靠性。每项都规定输入、实现产物、边界/故障用例及验收证据，贯穿 M1–M4，而不是只增加阅读书目。

## 范围与当前深度

- **主线规划**：算法与系统基础、RISC-V/NPU、QEMU、自写模型、AI 编译、运行时和受限 Agent。
- **并行与系统扩展**：网络 CPU 服务可独立起步；Linux PCI/PCIe NPU、CXL Type 3 内存与放置实验逐阶段验收，RDMA 为进阶。
- **其他后续扩展**：LFS/RV64 Linux 实践、外部 EDA/SRAM/物理实现迁移、CNN/GNN、其他生成模型、Agent RL。
- **尚未建立系统课程**：多 GPU/分布式训练、生产级服务集群、完整数据库、芯片制造与封装测试。
- **当前已验证起点**：Python INT8 GEMM、单 MAC RTL 及已有基线测试；新模块属于文档和实验规划。

首先打通一个线性层的量化与分块计划、C 运行时、QEMU/RTL 对照，再扩大到完整模型与 Agent。[整体规划](PROJECT_MAP.md) 给出依赖，[里程碑](ROADMAP.md) 给出验收顺序。

## 图片维护

V4 使用内置图像生成工具在 [V3](images/knowledge-coverage-v3.png) 基础上更新，[提示词](images/knowledge-coverage-v4.prompt.txt)保留主题、编号和文案。V1–V3 保留为历史资产。本轮未重新生成图片；十八个领域及编号不变，课程深度以更新后的文字索引为准。后续一级范围变化时再同步更新图片、课程与里程碑。
