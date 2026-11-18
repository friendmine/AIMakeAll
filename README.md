# AIMakeAll：数字 NPU 设计、模型研发与推理部署个人实训

本项目培养能够独立跨越三层工作的工程师：用 SystemVerilog 设计可综合的数字 NPU，从随机权重训练小型 Transformer，把模型部署到自己设计的加速器上。面对新负载，学习者要能定位误差或性能瓶颈，动手修改电路、模型或执行计划，并用同一任务复验。[个人培养规划与毕业标准](docs/CHIP_MODEL_PLAN.md#个人毕业任务)

例如，Transformer 的前馈层宽度同时影响模型容量、权重字节数和矩阵形状。课程先用模型的真实张量选择阵列和片上存储，再用 RTL 仿真记录访存与停顿，回到模型端比较宽度或量化方案。最终用同一组任务的模型质量和硬件代价说明取舍。[芯模联动的实验与验收](docs/PROJECT_MAP.md#芯模联动的实验与验收)

项目仓库：[friendmine/AIMakeAll](https://github.com/friendmine/AIMakeAll)。教材以中文原创讲解为主，引用上游原始资料；实验优先支持普通电脑，不要求购买 FPGA 或 GPU。

**默认采用仿真与数字电路设计路线**：硬件模块交付可综合 RTL、测试台、波形与综合结果；系统功能通过 QEMU/Linux 和虚拟网络验证。核心课程不依赖板卡或流片，高速 PHY/SerDes 使用接口模型，详见 [仿真优先与数字电路交付原则](docs/SIMULATION_FIRST.md)。

## 一个人从哪里开始

先做[实验 00](labs/00-int8-matmul/README.md)，用纸笔解释一个乘加，再做[实验 01 · 从第 257 项追到乘加器](labs/01-linear257/README.md)。后者从同一层权重出发，依次检查布局、分块、设备调用、整数输出和量化误差。只需 Python 即可开始，随后逐步加入 C、Verilator 和专用 QEMU。

[实验 02 · 给自己训练的模型设计一块乘加阵列](labs/02-trained-projection/README.md)将三项能力放进同一个任务。先训练能复述三个符号的 Transformer，把前馈层接入 4×4 阵列，再用测试困惑度和投影周期回答两个问题：电路要不要增加同时读取激活与权重的能力？模型能不能少用八个前馈通道？

| 想回答的问题 | 在仓库根目录运行 |
| --- | --- |
| 把一个模型层拆成两次设备命令，数值会改变吗？ | `make linear` |
| 同一层的训练比推理多保存什么？信号传输和助手纠错又如何验证？ | `make connections` |
| 一半内存还能完成原任务吗？ | 按[说明](simulator/qemu-v0/README.md)构建 QEMU 后运行 `make device-test design-trial` |
| 怎样复核真实训练权重在两种电路上的数值、访存和周期？ | `make projection-rtl`，可直接重放配套张量 |
| 改小模型后，留出集质量和推理开销如何变化？ | `make projection-train` 从零训练并接回 RTL，`make projection-synth` 检查电路结构 |

## 三项核心能力与应用扩展

数字 NPU 与模型是共同设计的两个对象。RISC-V 负责控制和提交任务，QEMU 提供驱动与功能验证环境，AI 编译与运行时负责将模型算子映射到电路支持的操作。完成整模型推理后，可用 Agent 作为扩展负载，观察推理优化对整个任务的影响。

| 阶段 | 要回答的问题 | 交付物 | 当前状态 |
| --- | --- | --- | --- |
| 1. RISC-V + NPU | CPU 如何把矩阵计算交给专用硬件？ | 开源 CPU 集成、INT8 NPU RTL、驱动、验证 | 单 MAC、含 16 个 MAC 的 4×4 阵列及两种局部存储已仿真、阵列已综合。RTL SoC 与 MMIO 待集成 |
| 2. QEMU Simulator | 软件如何在虚拟的加速器上运行？ | RISC-V 虚拟平台、NPU 设备模型、运行时、性能报告 | RV32 裸机已通过 MMIO 提交单层任务，完成两种预算与异常/复位检查 |
| 3. 从零训练 LLM | token 如何变成预测，模型如何映射到硬件？ | 自实现小型 Transformer、训练记录、量化导出、NPU 推理 | 已从零训练两种宽度的微型 Transformer，在复制任务上验证单投影 RTL 推理。字节语料小 LLM 及整机部署待实现 |
| 应用选修：Agent | 模型如何可靠调用工具完成任务？ | 工具协议、执行循环、评测集、端到端演示 | 已有基于真实运行报告的规则助手纠错练习，模型决策与独立任务评测待实现 |

这里的“从零”是自己实现并训练模型，从随机权重开始，不以下载预训练权重作为主线。教学模型首先追求可解释、可复现，不承诺达到通用商业助手水平。

## 知识覆盖图

![AIMakeAll 知识覆盖图 V9，十八个领域、已运行的单层实验与下一阶段](docs/images/knowledge-coverage-v9.png)

图中并列展示课程范围、已经运行的实验和后续主线。查看 [十八个领域的文字索引](docs/KNOWLEDGE_COVERAGE.md) 或 [全景规划](docs/PROJECT_MAP.md)；点击图片可查看原图。

现有十八个领域内保留十组、60 项待实现深化实验，包括 [计算机算术与算术电路结构 ARITH-E1–E6](docs/DIGITAL_DESIGN_TIMING.md#dd01dd02dd07-深化计算机算术与算术电路结构) 和 [硬件数据完整性与故障处置 RAS-E1–E6](docs/ARCHITECTURE.md#领域-04-与-17-深化硬件数据完整性与故障处置)，从位宽/乘法器推进到 MAC，从校验/ECC 推进到受保护存储和任务处置。保持一级目录与知识领域不变；全部十组的实验、交付物、验收和顺序见 [课程目录](docs/CURRICULUM.md) 与 [里程碑](docs/ROADMAP.md)。

另将 [跨层契约、资源预算、共同实验资产和教材学习者验证](docs/ROADMAP.md#四项共同交付的阶段安排) 贯穿现有课程：明确分阶段步骤、交付物和验收，首批从实验 00/FIFO 起步，再接单 Linear、模型和 Agent。实验 01 已生成分块哈希、逐项结果与两档预算记录，独立试读待执行。

已纳入 [芯片与 AI 全景课程的十条路线](docs/CHIP_AI_COMPLETENESS.md)：数学与信号、电路与器件、数字实践、CPU/GPU/DSP、物理实现与产品流程、跨层部署、经典机器学习与 AI、深度学习实证、感知控制与具身、分布式训练与服务。每条包含课程顺序、三个验收节点、交付物和仿真边界，按“全景通识 → 核心实践 → 专题深入”推进；30 个节点含既有实验的贯通验收，不与 60 项深化实验简单相加。DEP 已有固定形状的单层实例，模型级部署和其他路线按节点验收。

现有课程已加入 [六项跨层补强](docs/CHIP_AI_COMPLETENESS.md#六项跨层补强)：SoC 生命周期、硬件到模型信任链、数据变化后的可靠性、不同 AI 方法比较、理论边界、模拟与混合信号角色。各三个分步验收节点，全部待实施，复用既有实验；当前交付状态统一见 [课程状态总表](docs/CURRICULUM.md#课程状态总表)。首个 Linear 的核心路径保持不变，深入专题按需学习。

课程还包括 [实时系统、多模态与表示学习、因果推断](docs/CHIP_AI_COMPLETENESS.md#实时-多模态与因果课程)，各三个节点；新增 [从需求出发的整体设计取舍综合实验](docs/CHIP_AI_COMPLETENESS.md#design-从需求出发的整体设计取舍)，依次冻结需求、列候选、收集证据、做选择并迁移。实验 01 提供 DESIGN 的首个单层预算对照。完整模型、用户任务和三门专题仍按各自的验收标准推进。

## 从这里开始

先看 [整个项目的全景规划图](docs/PROJECT_MAP.md)：算法支撑组织与调度，CSAPP/OSTEP/LFS 分别连接程序、系统原理与构建，UDL/MiniMind 连接理论与训练，AI 编译将模型映射到运行时和 NPU。

1. 阅读 [项目路线与里程碑](docs/ROADMAP.md)。
2. 阅读 [系统架构与加速边界](docs/ARCHITECTURE.md)。
3. 完成 [实验 00：INT8 矩阵乘法与 MAC](labs/00-int8-matmul/README.md)。
4. 按 [课程目录](docs/CURRICULUM.md) 进入芯片设计、模型研发和推理部署课程。
5. 复用已有芯片开发环境前，阅读 [本地 EDA 软件、依赖与接入分析](docs/LOCAL_EDA_ENVIRONMENT.md)。
6. 整理重复工具安装时，按 [EDA 工具链统一方案](docs/EDA_TOOLCHAIN_CONSOLIDATION.md) 完成迁移与验收。
7. 进入模型与 Agent 阶段时，阅读 [MiniMind 学习与 NPU 接入方案](docs/MINIMIND_INTEGRATION.md)，对照完整训练流程。
   从零实现先参考 [Build a Large Language Model (From Scratch) 的七章及附录映射](models/README.md)，逐步完成文本、注意力、GPT、训练与微调，再对照 MiniMind。
8. 按阶段学习 [CSAPP 全书知识体系与项目实验](docs/CSAPP_FOUNDATIONS.md)，覆盖数值、处理器、存储、链接、异常、I/O、网络与并发。
9. 学习 [Understanding Deep Learning 知识体系](docs/UDL_FOUNDATIONS.md)，覆盖 21 章与数学/概率附录，连接从零模型、MiniMind、NPU 部署和 Agent 评估。
10. 学习 [Linux From Scratch 知识体系](docs/LFS_FOUNDATIONS.md)，从工具链自举到 Linux 启动，再扩展到 RV64 QEMU 与 AI 服务；首版 RV32 裸机主线独立推进。
11. 补齐 [算法与数据结构](docs/ALGORITHMS_FOUNDATIONS.md)，实现计算图依赖、队列、内存索引和检索排序。
12. 学习 [OSTEP 操作系统原理](docs/OSTEP_FOUNDATIONS.md)，连接调度、地址空间、并发与持久化。
13. 完成 [AI 编译学习路线](docs/AI_COMPILATION.md)：有限计算图 → 量化/分块 → 内存规划 → 执行计划 → C/QEMU/RTL 对照。
14. 按 [四个工程专项](docs/ENGINEERING_BRIDGES.md) 补数值、数据、性能验证和检索可靠性的实验与验收。
15. 学习 [网络与分布式通信](docs/NETWORKING_FOUNDATIONS.md)，从双节点 CPU 服务进入远程推理与 Agent；不等待 NPU 完成。
16. 按 [I/O 与 PCIe](docs/PCIE_IO_FOUNDATIONS.md) 从片内 MMIO、EDU 驱动推进到 Linux 虚拟 PCIe NPU。
17. 进阶学习 [CXL 与异构内存](docs/CXL_MEMORY_FOUNDATIONS.md)，从独立 Type 3 内存实验进入模型内存放置；阶段安排见 [S0–S3 路线](docs/ROADMAP.md)。
18. 学习 [数字设计与时序](docs/DIGITAL_DESIGN_TIMING.md)，从同步 FIFO、流水线和复位进入综合、时序与按需开展的 CDC 实验。
19. 按 [系统化验证](docs/SYSTEMATIC_VERIFICATION.md) 建立需求、独立参考、断言、覆盖、形式/等价和故障回归证据。
20. 学习 [仿真建模与可信度](docs/SIMULATION_CREDIBILITY.md)，为同一实验建立功能/周期模型、确定性重放、校验与敏感性分析；三条课程按 G0–G3 贯穿项目。

```sh
make test       # Python 3.10+、宿主 C 编译器，使用 Python 标准库
make demo       # 输出确定性的 INT8 矩阵乘法结果
make rtl-test   # 可选：需要 Verilator、C++ 编译器和 make
make eda-doctor # 可选：只读盘点本地芯片开发环境与历史验收状态
```

## 目录

```text
docs/               总体路线、架构、课程、开源来源与贡献规范
hardware/rtl/       有符号 MAC 与带局部存储的 4×4 投影阵列
simulator/          QEMU v0 设备源码、构建与协议检查
runtime/            软件运行时路线
models/             教学 Transformer 实现与后续语言模型路线
agents/             Agent 协议与评测路线
specs/              各层共同遵循的接口草案
reference/          无第三方依赖的数学参考实现
labs/               可执行实验及讲解
tests/              参考实现测试与 RTL 测试台
tools/eda/          本地开源芯片工具链检查；不自动安装或运行外部实验
```

## 关于“加速”

QEMU 功能模拟本身不保证比宿主机原生推理快。项目要求分别报告客体 RISC-V 软件路径与模拟 NPU 路径的耗时、宿主机原生基线、RTL 周期数。未来可用宿主机优化矩阵库加速设备模拟，但这种加速不能当作真实 NPU 的性能。详见架构文档。

## 开源与复现

项目原创教材和一般代码采用 [MIT License](LICENSE)。QEMU 设备源文件、头文件及集成补丁采用 [GPL-2.0-or-later](simulator/qemu-v0/COPYING)。第三方代码、文档、数据与模型各自保留原许可证，不因本仓库的许可证而改变。依赖候选及核验要求见 [来源清单](docs/OPEN_SOURCE.md)。专用 QEMU 从固定校验和的上游压缩包在本地构建。

后续贡献遵循 [贡献约定](CONTRIBUTING.md)：每个章节必须有原理、实验、预期结果和验收证据；未实现内容必须显式标记。
