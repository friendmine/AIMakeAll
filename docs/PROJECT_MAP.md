# AIMakeAll 全景规划图

更新：2026-11-17。状态以本项目记录为准；外部实验成果不等于已经接入本项目，资料规划不等于功能实现。

```mermaid
flowchart TB
    ROOT[AIMakeAll<br/>中文教材 + 开源实现 + 实验与验收]

    subgraph FOUNDATION[共同基础]
        CS[CSAPP 全书体系已映射<br/>CS01–CS12 实验待实现]
        UDL[Understanding Deep Learning<br/>21 章与附录已映射，实验待实现]
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
    ROOT --> UDL
    ROOT --> EDA
    ROOT --> SPEC

    subgraph HARDWARE[M1 · RISC-V + NPU]
        MAC[已验证：Python GEMM 与单 MAC]
        ARRAY[下一步：4×4 阵列<br/>分块、局部存储、随机对照]
        SOC[RISC-V + 总线 + NPU + 驱动]
        PHYS[扩展：综合、布局布线、SRAM 接入<br/>FPGA / 流片按后续目标推进]
        MAC --> ARRAY --> SOC --> PHYS
    end

    C1 --> ARRAY
    SPEC --> MAC
    EDA -.验证与物理基础.-> PHYS

    subgraph SIM[M2 · QEMU 与软件运行时]
        QEMU[RISC-V 虚拟平台与自定义 NPU 设备]
        RT[C 运行时<br/>CPU / NPU 后端与错误处理]
        QEMU --> RT
    end

    C2 --> QEMU
    SPEC --> QEMU
    SOC -.共同 ABI 与向量.-> QEMU

    subgraph MODEL[M3 · 从零 LLM 与 MiniMind]
        LEARN[自写小模型 + MiniMind 参考<br/>资料已纳入，训练待实施]
        TRAIN[数据与 tokenizer → 预训练 → SFT<br/>随机权重、独立验证集]
        QUANT[FP32 基线 → INT8 量化与导出<br/>权重、scale、分块与 KV 管理]
        LEARN --> TRAIN --> QUANT
    end

    C1 --> LEARN
    U1 --> LEARN
    U1 --> TRAIN
    C2 -.内存与加载.-> QUANT
    DEPLOY[模型推理闭环<br/>CPU / QEMU / RTL 数值对照<br/>prefill 与 decode 分开评测]
    QUANT --> DEPLOY
    RT --> DEPLOY
    SOC -.硬件对照.-> DEPLOY
    U2 -.质量评估.-> DEPLOY
    U3 -.后续算子负载.-> ARRAY

    subgraph AGENT[M4 · Agent 与服务]
        TOOL[受限工具、协议、进程与并发<br/>计算、检索、实验结果查询]
        APP[自训练模型决策 + 工具执行<br/>加速后端接入与独立任务评测]
        TOOL --> APP
    end

    C3 --> TOOL
    C2 -.异常与取消.-> TOOL
    DEPLOY --> APP
    U2 --> APP
    APP --> DONE[最终交付<br/>教材、源码、可复现实验与结果<br/>数值 / 质量 / 性能 / 任务成功率]
    PHYS -.物理验收证据.-> DONE
```

## 下一步与并行关系

1. 硬件推进 4×4 阵列，结合 CS02/CS04/CS06 学习数值、控制与存储。
2. 同期建立 C 构建追踪与 UDL 线性回归/小 MLP 实验，再进入自写 Transformer 与 MiniMind 小模型 CPU 环境；两套基础按需学习，不等待全书读完。
3. 围绕 GEMM/MMIO 接口逐步建立 QEMU 设备与运行时，再接量化模型。
4. 最后把模型推理接入受限 Agent，补文件、网络、并发和故障处理。

SRAM 与物理实现为扩展线，其状态需独立核验；早期功能实验可使用行为内存。QEMU 功能模拟、宿主机提速和真实硬件加速分开报告。

## 详细路线

- [CSAPP 全书知识体系与项目实验](CSAPP_FOUNDATIONS.md)
- [Understanding Deep Learning 知识体系与项目实验](UDL_FOUNDATIONS.md)
- [课程目录](CURRICULUM.md) · [里程碑](ROADMAP.md) · [系统架构](ARCHITECTURE.md)
- [本地 EDA 环境](LOCAL_EDA_ENVIRONMENT.md) · [工具统一方案](EDA_TOOLCHAIN_CONSOLIDATION.md)
- [MiniMind 学习与部署](MINIMIND_INTEGRATION.md)
