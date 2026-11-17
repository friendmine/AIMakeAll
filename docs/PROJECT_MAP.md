# AIMakeAll 全景规划图

更新：2026-11-18。状态以 [课程状态总表](CURRICULUM.md#课程状态总表) 及对应验证记录为准；外部实验成果不等于已经接入本项目，资料规划不等于功能实现。

交付遵循 [仿真优先原则](SIMULATION_FIRST.md)：数字 RTL → 仿真 → 综合，系统与协议使用 QEMU/事务模型；可选数字物理设计仍在电脑内完成。核心验收不要求板卡或流片。

## 知识覆盖范围

![AIMakeAll 知识覆盖图 V7：十八个领域、十条路线与六项跨层补强](images/knowledge-coverage-v7.png)

V7 保留十八个知识领域与十条全景路线，在下部增加生命周期、信任、分布变化、方法比较、理论边界和混合信号六项补强；数字实践、单 Linear 和小模型继续作为核心路径。查看 [原图](images/knowledge-coverage-v7.png)、[文字索引](KNOWLEDGE_COVERAGE.md) 和 [完整课程与验收](CHIP_AI_COMPLETENESS.md)。

原十组 60 项深化实验继续保留；既有十路线 30 个节点与本轮六项 18 个节点包含实验复用，不简单累加实验数。所有新增路线只完成规划。全景通识覆盖十条路线及六项补强，核心实践优先 PRA/DEP/DLE，专题深入按前置与预算选择，一级目录不变。

## 项目实施依赖

```mermaid
flowchart TB
    ROOT[AIMakeAll<br/>中文教材 + 开源实现 + 实验与验收]

    subgraph FOUNDATION[共同基础]
        ALG[算法 AL01–AL10<br/>复杂度、容器、图与调度]
        OS[OSTEP OS01–OS12<br/>调度、内存、并发与持久化]
        CS[CSAPP 全书体系已映射<br/>CS01–CS12 实验待实现]
        LFS[Linux From Scratch<br/>11 章与附录已映射，实验待实现]
        UDL[Understanding Deep Learning<br/>21 章与附录 + MATH-E1–E6 数学基础]
        U1[模型核心<br/>表达、损失、梯度、优化、残差与注意力]
        U2[评估与能力边界<br/>泛化、消融、伦理；RL 后续扩展]
        U3[广度选修<br/>CNN、GNN、生成模型]
        C1[第 1–6 章<br/>数值、机器代码、处理器、性能、存储]
        C2[第 7–9 章<br/>链接、异常控制流、虚拟内存]
        C3[第 10–12 章<br/>I/O、网络、并发]
        EDA[外部已有 EDA 实验基础<br/>工具统一方案待实施]
        SPEC[项目已有数值规范与接口草案<br/>GEMM、MMIO、布局与错误语义]
        CS --> C1
        CS --> C2
        CS --> C3
        UDL --> U1
        UDL --> U2
        UDL --> U3
    end

    ROOT --> CS
    ROOT --> ALG
    ROOT --> OS
    ROOT --> LFS
    ROOT --> UDL
    ROOT --> EDA
    ROOT --> SPEC

    subgraph BREADTH[全景补全 · 全部待实施]
        SIG[SIG 数学与信号系统<br/>方程、采样、状态空间]
        CIR[CIR 电路与半导体器件<br/>MOS、CMOS、寄生与噪声]
        HET[HET CPU / GPU / DSP<br/>执行模型与数据流对照]
        CHIP[CHIP 物理与产品流程<br/>供电、测试、封装、良率模型]
        CLA[CLA 经典机器学习与 AI<br/>树、核、逻辑、概率与规划]
        DLE[DLE 推导与模型比较<br/>梯度、结构性质、生成模型]
        EMB[EMB 感知估计与控制<br/>视觉、音频、二维机器人]
        SCALE[SCALE 规模工程<br/>训练、分片、服务与恢复]
        SIG --> CIR --> CHIP
        SIG --> EMB
        CLA --> EMB
        DLE --> EMB
    end
    ROOT --> SIG
    ALG --> CLA
    UDL --> DLE
    ROOT --> HET
    ROOT --> SCALE

    subgraph STRENGTH[六项跨层补强 · 实验待实施]
        LIFE[LIFE SoC 生命周期<br/>启动、休眠唤醒、恢复与调试]
        TRUST[TRUST 硬件到模型信任链<br/>认证、授权、防回滚与更新]
        SHIFT[SHIFT 数据变化可靠性<br/>校准、拒答、监测与再验收]
        SELECT[SELECT AI 方法比较<br/>共同任务、多策略与成本]
        LIMIT[LIMIT 理论边界<br/>可计算、高效、学习与证明]
        MIX[MIX 混合信号系统角色<br/>模拟前端、转换、时钟与误差]
        LIFE -.启动与恢复契约.-> TRUST
    end
    ROOT --> STRENGTH
    ALG -.复杂度与命题.-> LIMIT
    SIG --> MIX
    CIR --> MIX
    MIX -.信号到任务.-> EMB
    CLA --> SELECT
    DLE --> SELECT
    DLE --> SHIFT

    subgraph METHODS[设计、验证与仿真方法 · 实验待实现]
        DD[DD01–DD08 + PPA / ARITH<br/>数字设计、算术结构、时序与面积能耗]
        DV[DV01–DV08 + SW-E1–E6<br/>验证、软件正确性与可复现工程]
        SCM[SIM01–SIM08<br/>事件、周期、重放、校验与敏感性]
        FIFO[G0 / G1 共同起点<br/>PRA-1/2 同步 FIFO、调试、综合与证据]
        EVID[G2 / G3 证据报告<br/>DEP 单 Linear 对照、扩展与可信度]
        ARITH[ARITH-E1–E6 · 待实现<br/>位宽 → 加法器/乘法器 → 定点与 MAC]
        RAS[RAS-E1–E6 · 待实现<br/>校验/ECC → 受保护存储 → 故障处置]
        DD --> FIFO
        DV --> FIFO
        SCM --> FIFO
        FIFO --> EVID
        DD --> ARITH
        DV --> RAS
        ARITH -.数值与事务对照.-> EVID
        RAS -.G3 错误与恢复证据.-> EVID
    end

    ROOT --> DD
    ROOT --> DV
    ROOT --> SCM
    SPEC -.数值与接口约束.-> DV

    subgraph HARDWARE[M1 · RISC-V + NPU]
        MAC[已验证：Python GEMM 与单 MAC]
        ARRAY[下一步：4×4 阵列<br/>ARCH-E1/E2 数据流、局部存储与 bank]
        SOC[RISC-V + 总线 + NPU + 驱动<br/>MEM-E 事务、仲裁与存储模型扩展]
        PHYS[扩展：综合、布局布线、SRAM 接入<br/>电脑内物理设计；实物独立可选]
        MAC --> ARRAY --> SOC --> PHYS
    end

    C1 --> ARRAY
    ARITH -.候选结构经验证后接入.-> ARRAY
    SOC -.存储接口具备后扩展.-> RAS
    FIFO -.复用握手与验证方法.-> ARRAY
    SPEC --> MAC
    EDA -.验证与物理基础.-> PHYS
    DD -.复位与状态机.-> LIFE
    LIFE -.平台管理扩展.-> SOC
    LIMIT -.假设与证明范围.-> DV
    CIR -.器件与负载基础.-> DD
    DD -.已验模块.-> CHIP
    CHIP -.电脑内物理实验.-> PHYS
    HET -.架构对照.-> ARRAY

    subgraph SIM[M2 · QEMU 与软件运行时]
        QEMU[RISC-V 虚拟平台与自定义 NPU 设备]
        RT[C 运行时<br/>SW-E 正确性与 PERF-E 性能基准]
        QEMU --> RT
    end

    C2 --> QEMU
    OS -.内存与请求生命周期.-> RT
    SPEC --> QEMU
    SCM -.时间与重放契约.-> QEMU
    DV -.需求与测试追溯.-> QEMU
    SOC -.共同 ABI 与向量.-> QEMU
    DV -.SW-E 软件与复现证据.-> RT

    subgraph CONNECT[互连、通信与内存系统 · 实验待实现]
        IOBASE[S0 · IO01 片内互连<br/>MMIO 闭环、握手与访问边界]
        PCIBASE[S1 · IO02–IO04<br/>Linux EDU、BAR、DMA 与中断]
        PCINPU[S1 · IO05<br/>虚拟 PCIe NPU 与独立传输 ABI]
        NETBASE[S2 · NET01–NET04 · 可并行<br/>网络协议、双节点 CPU 服务与故障]
        NETAPP[S2 · NET05<br/>远程推理与 Agent，设备后端另验]
        CXL[S3 · CX01–CX05<br/>Type 3 与 ARCH-E6 分层放置]
        ADV[进阶 IO06 / NET06 / CX06<br/>PCIe RTL、软件 RDMA、CXL 状态模型<br/>连接 ARCH-E3–E5 缓存与可见性]
        IOBASE -.学习顺序.-> PCIBASE
        PCIBASE --> PCINPU
        PCIBASE -.PCI 与内存基础.-> CXL
        NETBASE --> NETAPP
        PCINPU -.可选远程 NPU 后端.-> NETAPP
        PCINPU --> ADV
        CXL --> ADV
        NETAPP --> ADV
    end

    SOC -.S0 验收.-> IOBASE
    C3 --> NETBASE
    OS -.并发与恢复.-> NETBASE
    OS -.内存原理.-> CXL
    ROOT --> CONNECT
    DD -.数字子模块.-> ADV
    DV -.协议与故障验收.-> ADV
    SCM -.模型边界与校验.-> ADV

    subgraph LINUX[系统扩展 · Linux 构建与服务，待实施]
        LXBASE[Linux x86-64 环境复现 LFS<br/>工具链 → 用户态 → 内核与启动]
        LXRV[独立 RV64 QEMU Linux<br/>固件、设备树与 rootfs 适配]
        LXDRV[Linux NPU 驱动<br/>缓冲区、用户接口与错误回收]
        LXSVC[推理与工具服务<br/>启动依赖、权限、日志与重启]
        LXBASE -.构建方法迁移.-> LXRV
        LXRV --> LXDRV --> LXSVC
    end

    LFS --> LXBASE
    OS -.系统机制.-> LXBASE
    C2 -.系统原理.-> LXBASE
    SPEC -.数值与设备语义.-> LXDRV
    LXDRV -.Linux 后端.-> RT
    LXRV -.独立 Linux PCIe 环境.-> PCINPU
    PCINPU -.设备后端.-> RT

    subgraph MODEL[M3 · 从零 LLM 与 MiniMind]
        LEARN[自写小模型 + MiniMind 参考<br/>资料已纳入，训练待实施]
        TRAIN[数据与 tokenizer → 预训练 → SFT<br/>随机权重、独立验证集]
        LEARN --> TRAIN
    end

    subgraph COMPILE[AI 编译 AC01–AC12 · 待实现]
        GRAPH[有限计算图<br/>依赖、形状、类型检查]
        QUANT[FP32 基线 → INT8 量化<br/>权重布局、scale 与校准规则]
        TILE[布局与 GEMM 分块<br/>K 部分和、CPU 回退]
        MEMORY[生命周期与缓冲区规划]
        PLAN[执行计划与模型包<br/>先单 Linear，再扩展模型]
        GRAPH --> QUANT --> TILE --> MEMORY --> PLAN
    end

    TRAIN --> GRAPH
    ALG --> GRAPH

    C1 --> LEARN
    U1 --> LEARN
    U1 --> TRAIN
    C2 -.内存与加载.-> QUANT
    DEPLOY[模型推理闭环<br/>CPU / QEMU / RTL 数值对照<br/>prefill 与 decode 分开评测]
    PLAN --> DEPLOY
    TRUST -.包认证与版本约束.-> RT
    RT --> DEPLOY
    EVID -.G2 验收.-> DEPLOY
    CXL -.CPU 模型内存放置扩展.-> DEPLOY
    SOC -.硬件对照.-> DEPLOY
    U2 -.质量评估.-> DEPLOY
    U3 -.后续算子负载.-> ARRAY

    subgraph AGENT[M4 · Agent 与服务]
        TOOL[受限工具、协议与任务状态<br/>STATE-E1–E6 持久化、恢复与安全]
        APP[自训练模型决策 + 工具执行<br/>AGQ-E1–E6 检索、决策与质量评测]
        TOOL --> APP
    end

    C3 --> TOOL
    ALG -.索引与任务队列.-> TOOL
    OS -.并发与恢复.-> TOOL
    C2 -.异常与取消.-> TOOL
    DEPLOY --> APP
    NETAPP -.远程服务扩展.-> APP
    U2 --> APP
    CLA -.推理与规划基线.-> APP
    EMB -.具身专题独立验收.-> APP
    DLE -.推导与比较证据.-> LEARN
    NETBASE -.通信前置.-> SCALE
    TRAIN -.训练前置.-> SCALE
    SCALE -.分布式部署扩展.-> LXSVC
    SHIFT -.监测与更新.-> SCALE
    SELECT -.同任务对照.-> APP
    TRUST -.执行授权.-> TOOL
    LXSVC -.后续部署环境.-> APP
    APP --> DONE[最终交付<br/>教材、源码、可复现实验与结果<br/>数值 / 质量 / 性能 / 任务成功率]
    PHYS -.物理验收证据.-> DONE
    EVID -.G3 分层证据.-> DONE
    ENG[四个工程专项 · 实验待实现<br/>数值量化、数据训练、性能验证、检索可靠性]
    ROOT --> ENG
    ENG -.贯穿 M1–M4 的验收.-> DONE
```

## 全景补全如何接入主线

课程顺序、30 个节点的产物与验收以 [全景课程补全](CHIP_AI_COMPLETENESS.md) 为准，阶段出口见 [里程碑](ROADMAP.md#十条全景补全路线的阶段安排)。SIG → CIR → CHIP 连起连续系统、器件、数字实现和产品认知；HET 与 ARCH/MEM/PERF 形成异构架构比较；CLA/DLE → EMB 连起感知、推断与行动；SCALE 接 M3 训练和 S2 网络进入服务工程。

PRA 复用图中 FIFO/阵列，DEP 复用单 Linear 与模型部署，DLE 复用 UDL/训练路线。它们承担实际能力出口，其余专题可先通识后深入。SPICE、电源/封装/良率模型、CPU 多进程与二维机器人仿真各自注明抽象层，不要求购买设备，也不代替电气、量产或真实集群验收。

## 六项补强的推进顺序

[六项实验规范](CHIP_AI_COMPLETENESS.md#六项跨层补强) 按 [阶段安排](ROADMAP.md#六项跨层补强的阶段安排) 接入：G0 先 LIMIT 命题分类、TRUST 资产边界；G1 随 FIFO 做 LIFE 独立启动模型；M1/M2 接生命周期与加载认证，休眠/更新恢复按 G3 深入；M3 冻结小模型后做 SHIFT，M4 用 SELECT 比较方法；MIX 在 SIG/CIR 后以离线向量连接数字计算。

所有节点先完成最小正常案例，再边界/故障、迁移及独立学习者验收。原有十路线与六项补强复用共同资产，不同时铺开为必修；新的教学状态机/认证包/理想 ADC 不改变 NPU v0 或已有 MAC。当前只有规划与图文更新，尚无新增实验成果。

## 下一步与并行关系

| 既有部分 | 深化实验与入口 | 推进关系 |
| --- | --- | --- |
| 体系结构 / NPU / 内存 | [ARCH-E1–E6](ARCHITECTURE.md) | 数据流与 bank 随阵列和单 Linear；Cache/一致性模型独立，Linux DMA/CXL 放置随后端条件推进 |
| UDL 附录 / 算法 / 数值 | [MATH-E1–E6](UDL_FOUNDATIONS.md) | 不变量与矩阵先按需补齐，再梯度/优化/概率，数值与统计贯穿评估 |
| CSAPP / DV08 / 运行时 | [SW-E1–E6](SYSTEMATIC_VERIFICATION.md) | C 参考和环境清单 → 模型包校验 → 故障/自动检测 → 独立重建与跨层回归 |
| OSTEP / ENG04 / 网络与 Agent | [STATE-E1–E6](ENGINEERING_BRIDGES.md) | 规则 Agent + 权限 + 单机状态库 → 模拟副作用崩溃恢复 → 远端未知结果/安全故障 → 模型接入 |
| CSAPP / ENG03 / 运行时 | [PERF-E1–E6](ENGINEERING_BRIDGES.md) | 正确 C 基线 → 分块/SIMD/线程 → 多层性能报告；流水重叠需独立机制 |
| 体系结构 / S0 / 仿真 | [MEM-E1–E6](ARCHITECTURE.md) | 固定事务 → 两来源仲裁 → DRAM 调度 → 小 NoC 模型与联合瓶颈分析 |
| DD07 / ENG03 / 物理扩展 | [PPA-E1–E6](DIGITAL_DESIGN_TIMING.md) | 比较契约/面积/时序 → 活动核验 → 功耗/任务能量 → 多目标选择；依证据分层 |
| ENG04 / 模型评估 / Agent | [AGQ-E1–E6](../agents/README.md) | 标注/检索 → 上下文/动作/终止 → 多步策略 → 质量成本消融；规则先行 |
| CS02 / DD / 数值与 PPA | [ARITH-E1–E6](DIGITAL_DESIGN_TIMING.md#dd01dd02dd07-深化计算机算术与算术电路结构) | 位宽/加法器 → 迭代/并行乘法 → MAC 对照；定点重缩放独立，不扩 v0 指令 |
| MEM / DV / 运行时与状态 | [RAS-E1–E6](ARCHITECTURE.md#领域-04-与-17-深化硬件数据完整性与故障处置) | 校验/编码 → 受保护存储 → 上报/故障重放 → 正常 GEMM 完成后的处置扩展 |

各组均待实现，详细阶段门槛见 [里程碑中的接入节奏](ROADMAP.md)。先形成一个可验收的小闭环，不要求学完全部新子实验才启动主线。

PERF/MEM/PPA/AGQ 将复用 GEMM、FIFO、模型与任务资产；当前只有 GEMM/MAC 基础用例，其余资产待建设。PERF 提供公平基准，MEM 解释等待和搬运，PPA 在指定库/范围内比较资源与能耗，AGQ 判断计算与检索是否改善任务结果。第一批只补共同输入/计时/事务/设计范围和任务标注，随后沿下方原主线实现；无板卡和完整工艺分析也能推进功能闭环。

1. DD/DV/SIM 先共用 G0/G1 同步 FIFO，形成接口、参考、RTL、覆盖、故障与重放模板；并行推进 4×4 阵列，结合 CS02/CS04/CS06 和 ENG03 学习数值、控制、存储与验证。
2. 软件并行做 AL07 计算图检查、C 整数参考和单线性层的量化/分块计划；先有可检查的计划解释器，再考虑 MLIR。
3. 围绕 GEMM/MMIO 建立 QEMU 设备与运行时，打通单线性层的 CPU/QEMU/RTL 对照；ENG01/ENG03 分别验收数值和性能。
4. UDL 与 MiniMind 小模型训练可并行，先补 ENG02 数据与恢复实验；模型成熟后复用同一编译与运行时路径。
5. Agent 接入 AL04/AL06 的索引和队列、OSTEP 的并发与持久化、ENG04 的检索和故障评估。
6. LFS/RV64 Linux 按独立系统扩展推进；OSTEP 原理实验不等待完整 LFS，Linux 扩展也不阻塞 RV32 裸机闭环。
7. IO01 随主线补片内访问与握手；IO02–IO05 用独立 Linux 环境从 EDU 进入 PCIe NPU。NET01–NET04 可先用 CPU 服务并行，NET05 再接模型、Agent 与已验收的设备后端。
8. CXL 在 PCI/Linux 内存基础之后，以独立 x86-64 q35 + Type 3 起步；先容量和放置，再研究 NPU 可寻址性、Type 2 或多设备。网络补帧级 MAC/FIFO/CRC 数字实验，PCIe 补事务模型与可综合桥接，CXL 补译码/队列 RTL；软件 RDMA 和一致性模型为进阶，实物不作前置。

SRAM 与物理实现为扩展线，其状态需独立核验；早期功能实验可使用行为内存。QEMU 功能模拟、宿主机提速和真实硬件加速分开报告。

[G0–G3](ROADMAP.md) 是各阶段的证据门槛：契约 → FIFO → 单 Linear → 系统扩展。单时钟主线不等待 DD06 异步 FIFO 或 SIM08 实时联仿；工具尚未支持或尚未跑通的检查保留未验证状态。

## 贯穿全景的四项共同交付

下表补充图中 G0/G1 共同起点与 G2/G3 证据报告的实施要求，复用图中已有节点，不增加知识领域。四项均处于规划阶段；具体阶段门槛见 [路线安排](ROADMAP.md#四项共同交付的阶段安排)。

| 工作 | 在现有主线中的作用 | 交付与推进顺序 |
| --- | --- | --- |
| [跨层契约](SYSTEMATIC_VERIFICATION.md#跨层契约的实施与验收) | 连接模型、编译、运行时、QEMU/RTL | 规范/版本登记 → 加载校验与能力清单 → 同资产差分 → 首个分歧与升级回归 |
| [资源预算](ENGINEERING_BRIDGES.md#资源预算的实施与验收) | 约束仿真、训练、部署与 Agent 规模 | 最小档上限 → 静态生命周期账本 → 有界短跑实测 → 决定扩展/缩小/后置 |
| [共同实验资产](ENGINEERING_BRIDGES.md#共同实验资产的实施与验收) | 为各章节提供一致输入、独立期望和重放依据 | 矩阵/FIFO → 分块 Linear/坏包 → 训练划分 → 标注任务/存储与互连轨迹 |
| [教材学习者验证](CURRICULUM.md#教材学习者验证的实施与验收) | 检查读者能否独立运行、解释、迁移和排错 | 实验 00 任务单 → 作者干净环境复现 → 独立试读 → 修订复测，随后推广到各章 |

工程验收看功能、契约与预算证据；教材验收另看学习任务与试读记录。首批从现有实验 00 和计划中的 FIFO 开始，G2 才要求单 Linear 的跨层报告。全部资产/记录沿用现有目录；图中的主线和十八个领域保持不变，十组深化实验共享这些交付方法。ARITH/RAS 各自的资产、资源与学习任务按 [新增两组的阶段安排](ROADMAP.md#算术电路与数据完整性的接入节奏) 接入。

## 详细路线

模型学习分工进一步细化为：UDL 原理与数学 → [Build a Large Language Model (From Scratch) 逐步实现](../models/README.md) → MiniMind 工程对照 → AI 编译与 NPU 部署 → Agent 任务评估。本书归入既有领域 10 和图中自写小模型节点，七章/附录实验均待实现；一级领域与目录保持不变。

- [知识覆盖文字索引](KNOWLEDGE_COVERAGE.md)
- [数字设计 DD01–DD08](DIGITAL_DESIGN_TIMING.md) · [系统化验证 DV01–DV08](SYSTEMATIC_VERIFICATION.md) · [仿真可信度 SIM01–SIM08](SIMULATION_CREDIBILITY.md)
- [算法与数据结构](ALGORITHMS_FOUNDATIONS.md) · [OSTEP 操作系统原理](OSTEP_FOUNDATIONS.md)
- [AI 编译与单线性层贯通实验](AI_COMPILATION.md) · [四个工程专项](ENGINEERING_BRIDGES.md)
- [网络 NET01–NET06](NETWORKING_FOUNDATIONS.md) · [I/O 与 PCIe IO01–IO06](PCIE_IO_FOUNDATIONS.md) · [CXL CX01–CX06](CXL_MEMORY_FOUNDATIONS.md)
- [CSAPP 全书知识体系与项目实验](CSAPP_FOUNDATIONS.md)
- [Linux From Scratch 知识体系与系统扩展](LFS_FOUNDATIONS.md)
- [Understanding Deep Learning 知识体系与项目实验](UDL_FOUNDATIONS.md)
- [课程目录](CURRICULUM.md) · [里程碑](ROADMAP.md) · [系统架构](ARCHITECTURE.md)
- [本地 EDA 环境](LOCAL_EDA_ENVIRONMENT.md) · [工具统一方案](EDA_TOOLCHAIN_CONSOLIDATION.md)
- [MiniMind 学习与部署](MINIMIND_INTEGRATION.md)
