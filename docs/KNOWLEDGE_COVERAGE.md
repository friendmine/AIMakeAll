# AIMakeAll 知识覆盖范围

更新：2026-11-17。V4 的十八个领域保持不变，已有八组、48 个深化子实验，详见下方映射。本轮补入跨层契约、资源预算、共同实验资产和教材学习者验证四项共同交付安排，不新增领域或实验编号。DD/DV/SIM 的 24 个模块继续以同步 FIFO 为共同起点。覆盖表示已纳入学习规划，尚不代表实验完成。

![AIMakeAll 知识覆盖图 V4：十八个领域，新增数字设计、系统验证与仿真可信度](images/knowledge-coverage-v4.png)

## 十八个领域及阅读入口

V4 表示知识范围；交付方式统一按 [仿真优先原则](SIMULATION_FIRST.md)：数字电路设计与综合、协议/RTL 仿真、QEMU 系统模拟。实板与流片不作为核心要求；新增教学数字子模块不等于完整 PCIe/CXL 标准实现。

| 图中编号 | 领域 | 主要学习内容 | 文档入口 |
| --- | --- | --- | --- |
| 01 | 数学与数值 | 离散与证明、线性代数、微分、优化、概率信息量、数值与统计 | [UDL / MATH-E1–E6](UDL_FOUNDATIONS.md)、[ENG01](ENGINEERING_BRIDGES.md) |
| 02 | 算法与数据结构 | 复杂度、容器、排序、图、动态规划与索引 | [AL01–AL10](ALGORITHMS_FOUNDATIONS.md) |
| 03 | 编程与程序执行 | C/ABI、内存语义、所有权、复现、SIMD 与线程性能 | [CSAPP](CSAPP_FOUNDATIONS.md)、[SW-E](SYSTEMATIC_VERIFICATION.md)、[PERF-E](ENGINEERING_BRIDGES.md) |
| 04 | 体系结构与加速器 | RISC-V/NPU、数据流、缓存、一致性、DRAM 调度、片上互连与面积/能耗 | [硬件](../hardware/README.md)、[ARCH-E / MEM-E](ARCHITECTURE.md)、[PPA-E](DIGITAL_DESIGN_TIMING.md) |
| 05 | 操作系统原理 | 调度、虚拟内存、同步、文件系统、事务恢复与权限 | [OS01–OS12](OSTEP_FOUNDATIONS.md)、[状态实验](ENGINEERING_BRIDGES.md) |
| 06 | Linux 系统构建 | 工具链、用户态、内核、rootfs、启动和服务 | [LFS](LFS_FOUNDATIONS.md) |
| 07 | 模拟器与驱动 | QEMU、虚拟设备、MMIO、中断和 DMA | [模拟器](../simulator/README.md)、[NPU 规范](../specs/npu-v0.md) |
| 08 | AI 编译 | 计算图、IR、布局/量化、分块、内存及执行计划 | [AC01–AC12](AI_COMPILATION.md) |
| 09 | 深度学习基础 | 模型表达、损失、梯度、优化与泛化 | [UDL](UDL_FOUNDATIONS.md) |
| 10 | 从零 LLM | 数据、分词、GPT 逐层实现、预训练、分类/指令微调 | [模型 / LLMs From Scratch 七章映射](../models/README.md)、[MiniMind](MINIMIND_INTEGRATION.md)、[ENG02](ENGINEERING_BRIDGES.md) |
| 11 | 推理运行时 | 计划、校验/所有权、KV、优化 CPU 后端、并行开销与设备调用 | [运行时](../runtime/README.md)、[AI 编译](AI_COMPILATION.md)、[PERF-E](ENGINEERING_BRIDGES.md) |
| 12 | Agent 与检索 | 排序/上下文、计划/终止、质量消融、权限、持久状态与恢复 | [Agent / AGQ-E](../agents/README.md)、[STATE-E1–E6](ENGINEERING_BRIDGES.md) |
| 13 | 网络与分布式通信 | Ethernet/TCP/IP、Socket/RPC、背压与重试、RDMA 进阶 | [NET01–NET06](NETWORKING_FOUNDATIONS.md) |
| 14 | I/O 与 PCIe | 片内互连、枚举/BAR、DMA/IOMMU、中断与 Linux 驱动 | [IO01–IO06](PCIE_IO_FOUNDATIONS.md) |
| 15 | CXL 与异构内存 | 协议与一致性、Type 3、地址译码、NUMA 与模型内存放置 | [CX01–CX06](CXL_MEMORY_FOUNDATIONS.md) |
| 16 | 数字设计与时序 | HDL、流水线/FIFO、CDC、综合/STA、活动与功耗面积权衡 | [DD01–DD08 / PPA-E](DIGITAL_DESIGN_TIMING.md) |
| 17 | 系统化验证 | 需求追溯、参考/断言、形式/等价、程序检测、故障/模糊测试与复现 | [DV01–DV08 / SW-E1–E6](SYSTEMATIC_VERIFICATION.md) |
| 18 | 仿真建模与可信度 | 模型边界、事件调度、周期/事务、重放、校验/校准与敏感性 | [SIM01–SIM08](SIMULATION_CREDIBILITY.md) |

图中中断、DMA、Linux 驱动等表示课程范围；当前 NPU v0 首版仍为同步轮询，不据图示扩大设备能力。CSAPP、OSTEP、LFS 分别侧重程序视角、系统机制和系统构建。

网络连接节点，PCIe 连接主机与设备，CXL 连接扩展内存并引入一致性相关机制。新增模块按 [S0–S3 阶段](ROADMAP.md) 推进：S0 MMIO 闭环 → S1 PCI/PCIe → S3 CXL；S2 网络可先用 CPU 服务并行，远程 NPU 接入另需本地后端验收。

## 八组深化内容如何归入现有体系

| 深化内容 | 主要归属与实验入口 | 新增的验收证据 |
| --- | --- | --- |
| 体系结构与存储系统 | 04 → 05/08/11/14/15；[ARCH-E1–E6](ARCHITECTURE.md) | 访问/容量账本、周期与冲突、缓存轨迹、可见性反例、有限状态性质、设计空间报告 |
| 数学基础 | 01 → 02/09/16/18；[MATH-E1–E6](UDL_FOUNDATIONS.md) | 推导与反例、残差/梯度对照、条件数与收敛、概率指标、误差与统计波动 |
| 软件正确性与可复现工程 | 03/17 → 06/08/11/18；[SW-E1–E6](SYSTEMATIC_VERIFICATION.md) | C 数值语义、坏包拒绝、检测语料、资源回收、环境 manifest、跨层回归 |
| 持久状态与安全 | 05/12/13；[STATE-E1–E6](ENGINEERING_BRIDGES.md) | 权限边界、任务状态、崩溃恢复、未知结果处理、攻击/资源限制用例、脱敏审计 |
| 并行计算与性能工程 | 02/03/04/11/18；[PERF-E1–E6](ENGINEERING_BRIDGES.md) | 同语义基线、向量化证据、线程伸缩/同步、重叠条件与分层性能报告 |
| 存储控制器与片上互连 | 04 → 07/14/15/16/17/18；[MEM-E1–E6](ARCHITECTURE.md) | 地址/事务守恒、DRAM 时序、调度公平、仲裁 RTL、NoC 模型与联合瓶颈 |
| 功耗能耗与面积权衡 | 04/16/18；[PPA-E1–E6](DIGITAL_DESIGN_TIMING.md) | 同库面积/时序、活动覆盖、任务能量、低活动设计与条件性 Pareto 比较 |
| Agent 检索与决策质量 | 02/09/10/12；[AGQ-E1–E6](../agents/README.md) | 标注/留出任务、排序指标、引用依据、动作/终止、多步策略、质量与成本消融 |

以上为八组各六项的待实现子实验，不是八个新增一级领域。它们深化已有领域，不增加图中一级编号或仓库一级目录；详细实施顺序见 [整体规划](PROJECT_MAP.md) 和 [里程碑](ROADMAP.md)。领域覆盖图继续使用 V4，新增深度由本页文字索引表达。

## 方法课程与四个工程专项

DD/DV/SIM 是贯穿各领域的方法课程，按 [G0–G3 门槛](ROADMAP.md) 组织：契约 → 同步 FIFO → 单 Linear → 系统扩展。领域 04 关注计算体系结构与 NPU，领域 16 负责可复用数字设计基本功；领域 07 关注 QEMU/驱动，领域 18 负责模型适用性与结论可信度。两两连接，不重复计算实现进度。

[ENG01–ENG04](ENGINEERING_BRIDGES.md) 覆盖数值量化、数据训练、性能与系统验证、检索与 Agent 可靠性。每项都规定输入、实现产物、边界/故障用例及验收证据，贯穿 M1–M4，而不是只增加阅读书目。

## 知识覆盖如何转为可验收交付

| 共同工作 | 覆盖关系 | 验收证据入口 |
| --- | --- | --- |
| 跨层契约 | 连接 04/07/08/10/11，并由 17/18 检查 | [规范版本、能力、校验与差分](SYSTEMATIC_VERIFICATION.md#跨层契约的实施与验收) |
| 资源预算 | 贯穿硬件/仿真、训练、推理与 Agent | [静态账本、实测、上限及扩规模决策](ENGINEERING_BRIDGES.md#资源预算的实施与验收) |
| 共同实验资产 | 各领域共用输入、期望、数据划分和故障轨迹 | [资产 ID/哈希、独立参考与重放](ENGINEERING_BRIDGES.md#共同实验资产的实施与验收) |
| 教材学习者验证 | 贯穿全部章节，按学习路线逐章验收 | [作者复现、独立试读与迁移排错任务](CURRICULUM.md#教材学习者验证的实施与验收) |

这四项是既有课程的交付方法，尚待实施；不计为新增四个一级领域，也不增加八组深化实验的数量。V4 图片保留范围表达，实施关系由 [全景规划](PROJECT_MAP.md#贯穿全景的四项共同交付) 与 [阶段安排](ROADMAP.md#四项共同交付的阶段安排) 补充。

## 范围与当前深度

- **主线规划**：算法与系统基础、RISC-V/NPU、QEMU、自写模型、AI 编译、运行时和受限 Agent。
- **并行与系统扩展**：网络 CPU 服务可独立起步；Linux PCI/PCIe NPU、CXL Type 3 内存与放置实验逐阶段验收，RDMA 为进阶。
- **其他后续扩展**：LFS/RV64 Linux 实践、外部 EDA/SRAM/物理实现迁移、CNN/GNN、其他生成模型、Agent RL。
- **尚未建立系统课程**：多 GPU/分布式训练、生产级服务集群、完整数据库、芯片制造与封装测试。
- **当前已验证起点**：Python INT8 GEMM、单 MAC RTL 及已有基线测试；新模块属于文档和实验规划。

首先打通一个线性层的量化与分块计划、C 运行时、QEMU/RTL 对照，再扩大到完整模型与 Agent。[整体规划](PROJECT_MAP.md) 给出依赖，[里程碑](ROADMAP.md) 给出验收顺序。

## 图片维护

V4 使用内置图像生成工具在 [V3](images/knowledge-coverage-v3.png) 基础上更新，[提示词](images/knowledge-coverage-v4.prompt.txt)保留主题、编号和文案。V1–V3 保留为历史资产。本轮未重新生成图片；十八个领域及编号不变，课程深度以更新后的文字索引为准。后续一级范围变化时再同步更新图片、课程与里程碑。
