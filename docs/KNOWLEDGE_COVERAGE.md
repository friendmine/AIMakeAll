# AIMakeAll 知识覆盖范围

十八个技术领域按三项个人能力取用。设计数字 NPU 时进入体系结构、存储、RTL、时序与验证；研发模型时进入数学、算法、训练与评测；部署推理时进入量化、编译、运行时与驱动。三条线通过一个已训练模型层的张量、硬件轨迹和质量结果汇合。[个人能力全景](PROJECT_MAP.md#个人如何贯通三项能力)

更新：2026-11-18。V9 沿用十八个领域、十组深化实验、十条全景路线与六项跨层补强，包括 RT/MM/CAUSE 三门各三个节点及 DESIGN 综合实验四个检查点。节点复用既有实验，不合计为无重叠的实验总数；交付状态见 [课程状态总表](CURRICULUM.md#课程状态总表)。固定形状 Linear 已交付可运行教材和预算迁移任务，独立学习者验证待执行。

![AIMakeAll 知识覆盖图 V9，十八个领域、已运行的单层实验与下一阶段](images/knowledge-coverage-v9.png)

## 十八个领域及阅读入口

V9 上半部索引十八个知识领域，中部展示固定线性层的四条算术路径与两种分块，下部展示四个配套练习、已训练投影的芯模联合实验和实验 03 的整机生成。数字电路、设备接口与系统软件分别使用 RTL 仿真与综合、QEMU 等工具验证。[仿真优先原则](SIMULATION_FIRST.md)

| 图中编号 | 领域 | 主要学习内容 | 文档入口 |
| --- | --- | --- | --- |
| 01 | 数学与数值 | 离散与证明、线性代数、微分、优化、概率信息量、数值统计、位宽与舍入、微分方程、信号与系统、有限样本保证、因果识别与估计 | [CAUSE](CHIP_AI_COMPLETENESS.md#cause-因果推断)、[SIG](CHIP_AI_COMPLETENESS.md#sig-数学与信号系统)、[LIMIT/MIX](CHIP_AI_COMPLETENESS.md#六项跨层补强)、[UDL / MATH-E1–E6](UDL_FOUNDATIONS.md)、[ENG01](ENGINEERING_BRIDGES.md)、[ARITH](DIGITAL_DESIGN_TIMING.md) |
| 02 | 算法与数据结构 | 复杂度、容器、排序、图、动态规划、搜索与约束规划、可计算性边界 | [CLA](CHIP_AI_COMPLETENESS.md#cla-传统机器学习与经典-ai)、[AL01–AL10](ALGORITHMS_FOUNDATIONS.md)、[LIMIT/SELECT](CHIP_AI_COMPLETENESS.md#六项跨层补强) |
| 03 | 编程与程序执行 | C/ABI、内存语义、所有权、复现、SIMD 与线程性能 | [CSAPP](CSAPP_FOUNDATIONS.md)、[SW-E](SYSTEMATIC_VERIFICATION.md)、[PERF-E](ENGINEERING_BRIDGES.md) |
| 04 | 体系结构与加速器 | RISC-V/NPU、算术结构、缓存/一致性、DRAM/互连、数据完整性、CPU/GPU/DSP 对照、生命周期与面积/能耗 | [HET](CHIP_AI_COMPLETENESS.md#het-cpu-gpu-dsp-对照)、[LIFE](CHIP_AI_COMPLETENESS.md#六项跨层补强)、[硬件](../hardware/README.md)、[ARCH / MEM / RAS](ARCHITECTURE.md)、[ARITH / PPA](DIGITAL_DESIGN_TIMING.md) |
| 05 | 操作系统原理 | 调度、虚拟内存、同步、文件系统、事务恢复与权限、实时调度/阻塞/时限 | [RT](CHIP_AI_COMPLETENESS.md#rt-实时系统)、[OS01–OS12](OSTEP_FOUNDATIONS.md)、[状态实验](ENGINEERING_BRIDGES.md) |
| 06 | Linux 系统构建 | 工具链、用户态、内核、rootfs、启动和服务；连接恢复与信任链 | [LFS](LFS_FOUNDATIONS.md)、[LIFE/TRUST](CHIP_AI_COMPLETENESS.md#六项跨层补强) |
| 07 | 模拟器与驱动 | QEMU、虚拟设备、MMIO、中断和 DMA | [模拟器](../simulator/README.md)、[NPU 规范](../specs/npu-v0.md) |
| 08 | AI 编译 | 计算图、IR、布局/量化、分块、内存及执行计划、设备贯通 | [DEP](CHIP_AI_COMPLETENESS.md#dep-编译运行时设备贯通)、[AC01–AC12](AI_COMPILATION.md) |
| 09 | 深度学习基础 | 模型表达、损失、梯度、泛化；扩展树/核/聚类、生成比较、分布变化、表示与多模态融合 | [MM](CHIP_AI_COMPLETENESS.md#mm-多模态与表示学习)、[UDL](UDL_FOUNDATIONS.md)、[CLA / DLE / EMB](CHIP_AI_COMPLETENESS.md)、[SHIFT/SELECT/LIMIT](CHIP_AI_COMPLETENESS.md#六项跨层补强) |
| 10 | 从零 LLM | 数据、分词、GPT 逐层实现、预训练、分类/指令微调 | [模型 / LLMs From Scratch 七章映射](../models/README.md)、[MiniMind](MINIMIND_INTEGRATION.md)、[ENG02](ENGINEERING_BRIDGES.md) |
| 11 | 推理运行时 | 计划、校验/所有权、KV、优化 CPU 后端、并行开销、设备调用、包认证与版本切换 | [运行时](../runtime/README.md)、[AI 编译](AI_COMPILATION.md)、[PERF-E](ENGINEERING_BRIDGES.md)、[TRUST/SHIFT](CHIP_AI_COMPLETENESS.md#六项跨层补强) |
| 12 | Agent 与检索 | 排序/上下文、计划/终止、质量消融、权限、持久状态与恢复、逻辑/概率推理、方法比较、具身决策、跨模态检索与干预决策 | [MM/CAUSE](CHIP_AI_COMPLETENESS.md#实时-多模态与因果课程)、[CLA / EMB](CHIP_AI_COMPLETENESS.md)、[SELECT/TRUST](CHIP_AI_COMPLETENESS.md#六项跨层补强)、[Agent / AGQ-E](../agents/README.md)、[STATE-E1–E6](ENGINEERING_BRIDGES.md) |
| 13 | 网络与分布式通信 | Ethernet/TCP/IP、Socket/RPC、背压与重试、分布式训练/推理/服务、RDMA 进阶 | [SCALE](CHIP_AI_COMPLETENESS.md#scale-大规模-ai-工程)、[NET01–NET06](NETWORKING_FOUNDATIONS.md) |
| 14 | I/O 与 PCIe | 片内互连、枚举/BAR、DMA/IOMMU、中断与 Linux 驱动 | [IO01–IO06](PCIE_IO_FOUNDATIONS.md) |
| 15 | CXL 与异构内存 | 协议与一致性、Type 3、地址译码、NUMA 与模型内存放置 | [CX01–CX06](CXL_MEMORY_FOUNDATIONS.md) |
| 16 | 数字设计与时序 | HDL、加法器/乘法器/MAC、定点舍入、流水线/FIFO、CDC、综合/STA/PPA；连接器件、混合信号、生命周期与产品流程 | [CIR / PRA / CHIP](CHIP_AI_COMPLETENESS.md)、[LIFE/MIX](CHIP_AI_COMPLETENESS.md#六项跨层补强)、[DD / ARITH / PPA](DIGITAL_DESIGN_TIMING.md) |
| 17 | 系统化验证 | 需求追溯、参考/断言、形式/等价、程序检测、ECC/故障处置、DFT、信任与证明范围、部署差分与复现、需求追溯与设计取舍 | [DESIGN](CHIP_AI_COMPLETENESS.md#design-从需求出发的整体设计取舍)、[PRA / DEP / CHIP](CHIP_AI_COMPLETENESS.md)、[TRUST/LIMIT](CHIP_AI_COMPLETENESS.md#六项跨层补强)、[DV / SW / 算术与故障验证](SYSTEMATIC_VERIFICATION.md)、[RAS](ARCHITECTURE.md) |
| 18 | 仿真建模与可信度 | 模型边界、事件调度、周期/事务、重放、校验/校准、连续系统与具身仿真 | [SIG / CIR / EMB](CHIP_AI_COMPLETENESS.md)、[SIM01–SIM08](SIMULATION_CREDIBILITY.md) |

图中中断、DMA、Linux 驱动等表示课程范围；当前 NPU v0 首版仍为同步轮询，不据图示扩大设备能力。CSAPP、OSTEP、LFS 分别侧重程序视角、系统机制和系统构建。

网络连接节点，PCIe 连接主机与设备，CXL 连接扩展内存并引入一致性相关机制。新增模块按 [S0–S3 阶段](ROADMAP.md) 推进：S0 MMIO 闭环 → S1 PCI/PCIe → S3 CXL；S2 网络可先用 CPU 服务并行，远程 NPU 接入另需本地后端验收。

## 用同一案例查看已覆盖的深度

| 领域 | 可亲手验证的内容 | 接下来的边界 |
| --- | --- | --- |
| 03 / 04 / 07 / 08 / 11 / 16 / 17 | 让 RV32 客体驱动 QEMU 教学设备。对比 Python、C 和单 MAC 的每段整数，找出错误布局的第一个字节差异 | 完整 v0 数据通路、通用模型加载 |
| 01 / 09 / 10 | 从 Linear 梯度推导，进到两个微型 Transformer 的随机初始化训练、恢复、bigram 基线和留出集评估 | 自然语言语料、多层模型与泛化评估 |
| 04 / 08 / 10 / 11 / 16 / 17 / 18 | 用真实权重驱动 4×4 阵列并接回生成，固定硬件或模型比较困惑度、周期与局部读取字节 | 03 已将该投影接入共同 RV32 驱动并追踪到 EOS，04 已在同一台 PicoRV32 上测量纯 CPU 和 NPU 的整步周期，05 已验证权重布局、额外存储与回本，06 已验证运行时模型切换、尺度和坏包处置。[实验 06](../labs/06-model-switch/README.md) · [实验 05](../labs/05-weight-prepack/README.md) · [实验 04](../labs/04-rv32-performance/README.md) · [实验 02](../labs/02-trained-projection/README.md) · [实验 03](../labs/03-rv32-generation/README.md) |
| 01 / 13 / 17 | 压缩、量化和加入纠错冗余，核对 64、56、32、168 bit 各对应的表示契约 | 实际协议开销和随机信道评估 |
| 14 / 15 / 18 | 用反射模型改变负载、采样相位和衰减，绘制接收眼图 | 真实 PCIe/CXL 发射器、接收器与电气合规 |
| 11 / 12 / 17 | 从旧报告发现预算错引，纠正助手的证据或接管终止 | 独立用户试读及模型驱动决策评测 |

每行可用相同的[学生实验与迁移任务](../labs/01-linear257/README.md)进入。设备与软件的实际运行范围见[验证记录](VALIDATION.md)。

## 十组深化内容如何归入现有体系

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
| 计算机算术与算术电路结构 | 01/04/16 → 17/18；[ARITH-E1–E6](DIGITAL_DESIGN_TIMING.md#dd01dd02dd07-深化计算机算术与算术电路结构) | 位宽/舍入、加法器/乘法器穷举、事务等价、MAC 集成、同约束结构比较 |
| 硬件数据完整性与故障处置 | 04/17 → 07/11/14/15/16/18；[RAS-E1–E6](ARCHITECTURE.md#领域-04-与-17-深化硬件数据完整性与故障处置) | 奇偶漏检反例、SECDED、受保护存储、CE/UE 上报、故障重放与结果失效 |

以上为十组各六项的待实现子实验，不是十个新增一级领域。它们深化已有领域，不增加图中一级编号或仓库一级目录；详细实施顺序见 [整体规划](PROJECT_MAP.md) 和 [里程碑](ROADMAP.md)。V8 展示原领域与路线，并加入三门专题和综合设计；原十组深化实验仍以本表为准。

## 十条全景补全路线

详细课程、前置、30 个节点的交付物与验收见 [全景课程补全](CHIP_AI_COMPLETENESS.md)。DEP 已有固定算例的实测证据，三条实践路线复用既有计划，不重复计算完成度。

| 路线 | 补齐的范围 | 学习链与证据 |
| --- | --- | --- |
| SIG | 微分方程、信号与系统 | RC 解析/数值 → 采样卷积 → 状态空间/稳定性 |
| CIR | 电路分析、MOS、CMOS、寄生与噪声 | 手算/SPICE → 门电路 → PVT/负载/噪声 |
| PRA | 数字实现、调试、综合实践 | FIFO → 故障定位 → 阵列/事务与综合 |
| HET | 高性能 CPU、GPU、DSP | 提交/预测模型 → SIMT → FIR/定点/数据流对照 |
| CHIP | 工艺、标准单元、供电、测试、封装、良率 | 小模块物理流程 → PDN/热模型 → scan/RAM 测试/假设良率 |
| DEP | 模型、编译、运行时与设备贯通 | K=257 Linear → C/guest/QEMU → RTL/模型 |
| CLA | 传统机器学习、知识表示、逻辑/概率推理与规划 | 树/核/聚类比较 → 有限逻辑/规划 → Bayes/HMM |
| DLE | 推导、独立校验与模型比较 | 梯度三方对照 → 结构性质 → 低维生成模型比较 |
| EMB | 视觉/音频、传感、估计、控制与机器人 | 感知 → Kalman/反馈 → 二维机器人闭环 |
| SCALE | 分布式训练、多设备推理与生产服务 | CPU worker 聚合 → 分片/推理 → 有界负载/恢复/回滚 |

这些路线覆盖全景通识；主线实践优先 PRA/DEP/DLE，器件、物理、具身与集群方向按专题深入。真实电气、制造良率、机器人迁移与多 GPU 性能需独立证据，教学仿真不代替工业验收。

## 六项跨层补强及归属

[完整实验与验收](CHIP_AI_COMPLETENESS.md#六项跨层补强) 每项三个节点，全部待实施，归入已有课程。表中范围不暗示 NPU v0 已具备新能力。

| 补强 | 主要归属领域与既有路线 | 三步实验与证据 |
| --- | --- | --- |
| LIFE SoC 生命周期 | 04/06/07/16/17/18；PRA、CHIP、LFS、DD/SIM | 上电/启动状态 → 排空/睡眠/唤醒 → 看门狗/恢复/调试轨迹 |
| TRUST 硬件到模型信任链 | 03/05/07/08/11/12/17；DEP、SW、STATE | 威胁/认证包 → 启动/模型/防回滚 → 更新/撤销/恢复 |
| SHIFT 数据变化可靠性 | 01/09/10/11/12/13/17；DLE、SCALE、ENG02 | 分布变化 → 校准/拒答 → 监测/更新/再验收 |
| SELECT AI 方法比较 | 02/09/10/12/17；CLA、DLE、AGQ | 同任务资产 → 多策略基线 → 消融/质量成本/方法选择 |
| LIMIT 理论边界 | 01/02/09/17/18；AL、MATH、DV/SIM | 有界/无界命题 → 复杂度/UNKNOWN → 有限样本保证 |
| MIX 模拟与混合信号 | 01/04/09/16/18；SIG、CIR、HET、EMB | 放大/滤波/ADC/DAC → 噪声/抖动 → 数字计算/感知误差 |

先通识再按需实践；独立状态模型、标准签名工具、合成数据和信号仿真均可在电脑内完成。物理信任根、真实低功耗/转换器与抗攻击能力需另行证据。

## 实时 多模态 因果与需求驱动设计

[三门课程与综合实验的完整交付和验收](CHIP_AI_COMPLETENESS.md#实时-多模态与因果课程) 复用既有知识领域；RT/MM/CAUSE 各三个节点，DESIGN 是一个实验的四个检查点，预算减半已在单层案例运行。其余按节点验收。

| 内容 | 归属与已有连接 | 实验与证据 |
| --- | --- | --- |
| RT 实时系统 | 02/04/05/07/11/12/17/18；OSTEP、SIM、LIFE、EMB | RM/EDF/响应分析 → 优先级反转/继承 → 控制与推理分层；时限、错期、队列/数据年龄与降级 |
| MM 多模态与表示学习 | 01/08/09/10/11/12/17；DLE、ENG02、EMB、AGQ、DEP | 表示/配对 → 对比对齐/检索 → 融合/缺失/部署；划分、正例关系、质量/误差与成本 |
| CAUSE 因果推断 | 01/02/09/12/17/18；MATH、CLA、SHIFT | 观察与干预 → 识别/估计 → 反事实/决策；DAG/SCM、调整假设、重叠与不可识别反例 |
| DESIGN 需求驱动综合实验 | 04/08/09/11/12/16/17/18，按需 05/13/14/15；契约、预算、SELECT/PERF/PPA/DEP | 需求 → 候选 → 分层证据 → 取舍/迁移；REQ 追溯、质量/内存/时限、Pareto 与不可行结论 |

三门专题通过通识和小案例建立边界；主线用 DESIGN 验证“为什么选择这种模型/精度/后端/存储”。模拟器和小合成数据即可起步；真实硬实时、真实芯片能耗及开放世界多模态/因果能力须另行验证。

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

实验 01 已提供契约对照、预算、数据哈希、结果和评分任务，独立试读待执行；不计为新增四个一级领域，也不计入十组深化实验的数量。V8 底部展示四项共同交付，详细实施关系由 [全景规划](PROJECT_MAP.md#贯穿全景的四项共同交付) 与 [阶段安排](ROADMAP.md#四项共同交付的阶段安排) 补充。

## 范围与当前深度

- **主线规划**：算法与系统基础、RISC-V/NPU、QEMU、自写模型、AI 编译、运行时和受限 Agent。
- **并行与系统扩展**：网络 CPU 服务可独立起步；Linux PCI/PCIe NPU、CXL Type 3 内存与放置实验逐阶段验收，RDMA 为进阶。
- **其他后续扩展**：LFS/RV64 Linux 实践、外部 EDA/SRAM/物理实现迁移、CNN/GNN、其他生成模型、Agent RL。
- **全景与跨层规划**：既有电路/器件、信号/控制、异构架构、经典 AI、具身、规模与产品流程继续保留；六项跨层连接、实时、多模态、因果与需求驱动取舍仍列入课程。
- **仍超出核心范围**：完整数据库内核、先进工艺与模拟/RF 全领域、工业量产签核、真实大集群性能和真实机器人部署；后续按专题与证据拓展。
- **已运行的核心**包括实验 00、实验 01 的四条数值路径与设备检查、四个配套练习，以及实验 02 的微型 Transformer 训练、前馈投影 RTL 回放与混合生成，以及实验 03 的同固件整机生成、实验 04 的同机性能对照、实验 05 的权重预打包与实验 06 的双模型加载和缓存验证。

首先打通一个线性层的量化与分块计划、C 运行时、QEMU/RTL 对照，再扩大到完整模型与 Agent。[整体规划](PROJECT_MAP.md) 给出依赖，[里程碑](ROADMAP.md) 给出验收顺序。

## 图片维护

V9 使用可编辑的 [SVG 图源](images/knowledge-coverage-v9.svg) 和 [生成脚本](images/render-knowledge-coverage-v9.cjs)，导出 [PNG](images/knowledge-coverage-v9.png) 供仓库展示。十八个领域按 01–18 排列，图下方显示单层闭环、已运行练习与后续路线；图表示范围，不表示完成比例。脚本需 Node.js，PNG 导出另需 Sharp；它们仅用于文档图片维护，不是实验学习依赖。运行 `node docs/images/render-knowledge-coverage-v9.cjs` 生成 SVG，运行时追加 `--png` 同步导出 PNG；已有 Sharp 可通过 `NODE_PATH` 指向，不要求全局安装。

[V8](images/knowledge-coverage-v8.png)、[V7](images/knowledge-coverage-v7.png)、[V6](images/knowledge-coverage-v6.png)、[V5](images/knowledge-coverage-v5.png)、[V4](images/knowledge-coverage-v4.png) 及其 [提示词](images/knowledge-coverage-v4.prompt.txt)、V1–V3 保留为历史资产。后续修改同步图源、PNG、文字索引和里程碑，避免图片范围与实验状态脱节。
