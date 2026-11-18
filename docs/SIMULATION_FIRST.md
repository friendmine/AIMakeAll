# 仿真优先与数字电路交付原则

更新：2026-11-18。项目默认在普通电脑上完成学习、设计和验证，尽量减少实物工作。核心课程的验收不依赖购买开发板、网卡、CXL 内存、示波器或实际流片。本文约束 [整体规划](PROJECT_MAP.md)、[S0–S3 阶段](ROADMAP.md) 及后续实验实现；部分算术和功能模拟已运行，具体范围见[实验 01](../labs/01-linear257/README.md)。

## 交付方式

本原则由三条课程落实：[DD01–DD08 数字设计与时序](DIGITAL_DESIGN_TIMING.md) 负责电路与约束，[DV01–DV08 系统化验证](SYSTEMATIC_VERIFICATION.md) 负责正确性证据，[SIM01–SIM08 仿真建模与可信度](SIMULATION_CREDIBILITY.md) 负责模型边界、时间与结论。三者共用同步 FIFO，再迁移到单 Linear；按 [G0–G3](ROADMAP.md) 验收。单层功能数据已取得，FIFO、RTL 总线与完整阶段验收待推进。

硬件模块以可综合的 Verilog/SystemVerilog 为目标，先通过软件参考和 RTL 仿真，再做综合与可选物理设计。高层协议与系统服务使用软件或事务级模型，不强求把 Linux、TCP/IP 协议栈和模型训练全部转换成电路。

“生成数字电路”指从硬件描述到逻辑网表，进一步可生成布局布线结果；它不等于把任意 Python/C 模型自动转换成完整芯片。行为模型、测试台和 QEMU 设备代码通常不是可综合设计，必须与 DUT（被测硬件）分别标记。

| 验证层次 | 默认交付 | 证明什么 | 不能据此宣称什么 |
| --- | --- | --- | --- |
| 软件/事务参考 | Python/C 模型、协议事务、固定种子与预期结果 | 功能规则、地址/消息边界、算法一致性 | 已实现硬件时序或完整链路 |
| RTL 仿真 | 可综合 DUT、非综合测试台、断言、波形、随机/故障回归 | 选定时钟/复位和协议子集下的周期行为 | 已满足硅上频率、电气条件或完整标准合规 |
| 逻辑综合 | Yosys 脚本、网表、单元统计、未解析模块清单 | 目标工具支持的数字逻辑可以综合 | 物理时序收敛、封装/PHY 已完成 |
| 物理设计扩展 | 锁定开源 PDK/库、约束、布局布线与 STA/DRC 等报告 | 选定工艺和约束下的数字模块实现与估算 | 完整芯片签核、可量产或真实 PCIe/CXL 速率 |
| 系统模拟 | QEMU/Linux 配置、驱动、服务、应用轨迹 | 软件可以使用虚拟设备完成任务 | QEMU 自动执行 RTL，或虚拟耗时等于真实硬件性能 |

Verilator 将 HDL 转换成可执行 C++/SystemC 模型，适用于此项目的 RTL 仿真路线；Yosys 承担逻辑综合，二者交付不同。[Verilator 概述](https://verilator.org/guide/latest/overview.html)、[Yosys 介绍](https://yosyshq.readthedocs.io/projects/yosys/en/latest/introduction.html)

## 各领域的无板卡路径

| 领域 | 拟实现的数字部分 | 默认仿真方式与外部替身 | 首个验收 |
| --- | --- | --- | --- |
| RISC-V/NPU | MAC、阵列、FIFO、控制、片内总线和内存接口 | Verilator；行为 RAM；指令/算术参考模型 | CPU 发起 GEMM，结果与 Python/C 相同，复位/越界有证据 |
| 网络 | 帧收发、CRC、FIFO、流控、简化 MAC/NIC 数据路径 | 帧级/GMII 等数字接口测试模型；虚拟网络承载 Linux TCP/IP 与 RPC | 正常帧收发、坏 FCS/长度处理、队列背压与复位；无需网线/PHY |
| PCIe | BAR 寄存器、TLP 请求/完成处理子集、DMA 描述符与 NPU 桥 | Root Complex/Endpoint 事务模型提供主机与链路替身；QEMU 验证 Linux 软件路径 | memory read/write、完成匹配、地址边界、超时/复位；不冒充完整 PCIe Endpoint |
| CXL | 简化地址译码、请求/响应队列、内存控制路径；一致性状态机为进阶 | QEMU Type 3 验证软件；原创内存事务模型 + 行为 RAM 验证 RTL 子集 | 地址译码、数据读写、顺序/背压/复位；一致性另用有限状态模型验收 |
| LLM/Agent | 默认软件实现，通过运行时调用 NPU | 宿主 CPU 训练/推理、QEMU guest、虚拟网络与模拟工具 | 固定输入下的数值、质量、协议和任务指标 |

网络 PHY、PCIe/CXL SerDes、时钟恢复、均衡、封装和信号完整性以接口模型或范围说明处理，不列入核心课程必做项。部分 PHY 含可综合数字逻辑，但高速电气收发不能仅凭通用 RTL 综合证明可用。

## 连续系统与规模专题的仿真边界

[十条全景补全路线](CHIP_AI_COMPLETENESS.md) 继续采用无板卡路径：SIG 用数值积分/频谱，CIR 用 SPICE 器件与电路网表，CHIP 用开放物理流程及电源/封装/热/假设良率模型；EMB 用传感噪声与二维机器人仿真；SCALE 用 CPU 多进程模拟通信、训练与推理分片。PRA/DEP/DLE 分别复用 FIFO、单 Linear 和小模型进行贯通验收，DEP 的单层实例已运行。

SPICE/连续模型不要求变为可综合 RTL；物理流程、参数模型与真实器件分别标记证据等级。芯片制造良率、EM 可靠性、真实机器人迁移与多 GPU 性能需额外环境和实测，教学模拟不替代这些结论。

## 三条互连路线如何落实

### 网络：软件服务与数字数据路径并行

[NET01–NET05](NETWORKING_FOUNDATIONS.md) 在一台电脑的多个进程/guest 中完成。另安排 NET-H1 帧 FIFO 与 CRC、NET-H2 简化 MAC 收发、NET-H3 队列/寄存器与可选 DMA；这些为同一课程的硬件实验，不要求先设计完整 TCP/IP offload 引擎。

RTL 首先与测试台的帧源/接收端通信，Linux 服务先使用 QEMU 虚拟网卡。把自研 NIC RTL 接入 Linux 网络栈属于独立联调交付，不能把虚拟网卡成功视为自研 MAC 已集成。NET06 优先参数模型或 Linux 软件 RDMA；软件支持组合另验，不依赖 RDMA 实卡。

### PCIe：TLP 边界内实现电路，边界外使用模型

[IO02–IO05](PCIE_IO_FOUNDATIONS.md) 保留 Linux/QEMU 路线；IO06 改为“事务级与 RTL 仿真进阶”。第一版 RTL 桥在明确的 TLP/并行数字接口边界工作，先实现受限 memory read/write、BAR 与 NPU 寄存器，再扩 DMA/队列。主机枚举与完成事务由参考模型驱动；链路训练、重放、完整信用流控和物理编码不隐含为已实现，逐项标注支持范围。

每条 TLP 用例同时记录类型、地址、长度、tag、数据和响应；对照 RTL 与参考结果。Linux 虚拟设备和 RTL 桥使用共同寄存器/数值规范，两个实现分别验收，初期无需实时联合仿真。

### CXL：先功能系统，再数字子模块与一致性模型

[CX02–CX05](CXL_MEMORY_FOUNDATIONS.md) 用 QEMU Type 3 学习发现、译码和内存使用；CX-H1 另实现简化内存请求/响应参考模型，CX-H2 实现译码、队列与存储访问 RTL。明确使用原创教学接口，尚不能称为符合 CXL.mem 标准的控制器。

CX06 的一致性进阶先建有限状态模型与断言，例如单写者/多读者约束、数据可见性、失效确认后转移权限；活性检查写明公平性与响应假设。再按明确选定的标准子集映射到 RTL。QEMU 不模拟完整一致性协议，不能代替这些验证。[QEMU CXL 范围](https://www.qemu.org/docs/master/system/devices/cxl.html)

## 工具与工作顺序

1. 先复用现有 Python/C、Verilator 和 Yosys；参考 [本地 EDA 盘点](LOCAL_EDA_ENVIRONMENT.md) 固定每个实验的版本，不在本轮合并或升级本机安装。
2. 协议测试可评估 cocotb、[cocotbext-eth](https://github.com/alexforencich/cocotbext-eth) 和 [cocotbext-pcie](https://github.com/alexforencich/cocotbext-pcie)。这些是测试模型候选，不是已经选定的可综合 MAC/PCIe/CXL IP；实施前核对许可、模拟器支持和不可变提交。[cocotb 模拟器支持](https://docs.cocotb.org/en/stable/simulator_support.html)
3. 先做离线共同向量与事务对照，再考虑 QEMU ↔ RTL 联合仿真。联合仿真需另外实现时间推进、内存访问、事件/中断、复位和死锁处理的桥接，不能声称两个工具天然连通。
4. 逻辑综合作为新硬件模块的交付检查；门级/形式验证按协议风险补充。RTL 到 GDS 是可选数字物理设计实验，可在电脑完成，不要求制造芯片；复用外部流程前核验 PDK、宏与约束。
5. 每个实验记录支持子集、排除项、随机种子、输入/输出、波形或系统轨迹、资源/周期及可复现命令。工具运行时间、RTL 周期、参数化估算分别报告；虚拟容量和节点数也须受宿主资源预算约束。

FPGA 上板、真实 NIC/PCIe/CXL 设备与流片仅在后续另有目标时增加；缺少实测不阻止完成本项目的仿真与教学验收，但报告须保留其适用边界。现有可复现实验含 RV32/QEMU 功能设备、独立的 Verilator 单 MAC 重放与终端反射教学模型。后者支持调阻抗、衰减及采样相位，仅在给定模型条件下解释眼图。[学生实验](../labs/01-linear257/README.md)

## 六项补强的模型边界

[六项补强](CHIP_AI_COMPLETENESS.md#六项跨层补强) 分别采用平台生命周期状态机、可信存储/启动模型、合成变化数据、有限共同任务、数学/状态空间检查和模拟信号链。LIFE 的逻辑休眠不证明真实供电行为，TRUST 的普通文件不充当硬件信任根，MIX 的理想 ADC 不证明芯片 ENOB；LIMIT 明确有界、概率与无界结论。按模型/RTL/guest/数据范围分别登记，均待实施。
