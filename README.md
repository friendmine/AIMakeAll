# AIMakeAll：从 RISC-V + NPU 到 LLM 与 Agent

用可获取、可修改、可复现的开源资料，逐层理解并实现 AI 的完整系统：处理器、加速器、模拟器、训练与推理、Agent。

项目仓库：[friendmine/AIMakeAll](https://github.com/friendmine/AIMakeAll)。教材以中文原创讲解为主，引用上游原始资料；实验优先支持普通电脑，不要求购买 FPGA 或 GPU。

## 四条主线

| 阶段 | 要回答的问题 | 交付物 | 当前状态 |
| --- | --- | --- | --- |
| 1. RISC-V + NPU | CPU 如何把矩阵计算交给专用硬件？ | 开源 CPU 集成、INT8 NPU RTL、驱动、验证 | 路线已建立；MAC 入门实验可运行 |
| 2. QEMU Simulator | 软件如何在虚拟的加速器上运行？ | RISC-V 虚拟平台、NPU 设备模型、运行时、性能报告 | 接口与实现路线草案 |
| 3. 从零训练 LLM | token 如何变成预测，模型如何映射到硬件？ | 自实现小型 Transformer、训练记录、量化导出、NPU 推理 | 课程与验收标准已建立 |
| 4. Agent | 模型如何可靠调用工具完成任务？ | 工具协议、执行循环、评测集、端到端演示 | 课程与验收标准已建立 |

这里的“从零”是自己实现并训练模型，从随机权重开始，不以下载预训练权重作为主线。教学模型首先追求可解释、可复现，不承诺达到通用商业助手水平。

## 从这里开始

先看 [整个项目的全景规划图](docs/PROJECT_MAP.md)：CSAPP 系统基础贯穿硬件、模拟器、模型与 Agent。

1. 阅读 [项目路线与里程碑](docs/ROADMAP.md)。
2. 阅读 [系统架构与加速边界](docs/ARCHITECTURE.md)。
3. 完成 [实验 00：INT8 矩阵乘法与 MAC](labs/00-int8-matmul/README.md)。
4. 按 [课程目录](docs/CURRICULUM.md) 开始四阶段学习。
5. 复用已有芯片开发环境前，阅读 [本地 EDA 软件、依赖与接入分析](docs/LOCAL_EDA_ENVIRONMENT.md)。
6. 整理重复工具安装时，按 [EDA 工具链统一方案](docs/EDA_TOOLCHAIN_CONSOLIDATION.md) 完成迁移与验收。
7. 进入模型与 Agent 阶段时，阅读 [MiniMind 学习与 NPU 接入方案](docs/MINIMIND_INTEGRATION.md)，对照完整训练流程。
8. 按阶段学习 [CSAPP 全书知识体系与项目实验](docs/CSAPP_FOUNDATIONS.md)，覆盖数值、处理器、存储、链接、异常、I/O、网络与并发。

```sh
make test       # Python 3.10+，无第三方 Python 依赖
make demo       # 输出确定性的 INT8 矩阵乘法结果
make rtl-test   # 可选：需要 Verilator、C++ 编译器和 make
make eda-doctor # 可选：只读盘点本地芯片开发环境与历史验收状态
```

## 目录

```text
docs/               总体路线、架构、课程、开源来源与贡献规范
hardware/rtl/       教学硬件；目前只有有符号 MAC，不是完整 NPU
simulator/          QEMU 设备开发路线
runtime/            软件运行时路线
models/             从零训练与量化部署路线
agents/             Agent 协议与评测路线
specs/              各层共同遵循的接口草案
reference/          无第三方依赖的数学参考实现
labs/               可执行实验及讲解
tests/              参考实现测试与 RTL 测试台
tools/eda/          本地开源芯片工具链检查；不自动安装或运行外部实验
```

## 关于“加速”

QEMU 功能模拟本身不保证比宿主机原生推理快。项目分别报告：客体 RISC-V 软件路径与模拟 NPU 路径的耗时、宿主机原生基线、RTL 周期数。未来可用宿主机优化矩阵库加速设备模拟，但这种加速不能当作真实 NPU 的性能。详见架构文档。

## 开源与复现

原创代码和文档采用 [MIT License](LICENSE)。第三方代码、文档、数据与模型各自保留原许可证，不因本仓库的许可证而改变。依赖候选及核验要求见 [来源清单](docs/OPEN_SOURCE.md)。目前尚未引入上游硬件代码、QEMU 源码或训练数据。

后续贡献遵循 [贡献约定](CONTRIBUTING.md)：每个章节必须有原理、实验、预期结果和验收证据；未实现内容必须显式标记。
