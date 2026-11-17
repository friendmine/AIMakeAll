# 开源来源与引入规则

2026-11-17 建立。以下为上游候选清单，目前没有把这些项目的源码复制进仓库。链接用于追溯；实际引入时必须锁定提交，并核对对应版本 LICENSE、NOTICE 与文件级声明。

| 项目 | 用途 | 许可证概况/核验入口 |
| --- | --- | --- |
| [Ibex](https://github.com/lowRISC/ibex) | 首选 RV32 CPU 核 | Apache-2.0；以所选提交的 LICENSE/NOTICE 为准 |
| [QEMU](https://www.qemu.org/docs/master/system/target-riscv.html) | RISC-V 系统模拟 | 主要 GPL-2.0；各文件与所引入模块分别核验 |
| [Verilator](https://github.com/verilator/verilator) | RTL 仿真 | 查看上游 LICENSE 与生成代码相关条款 |
| [Yosys](https://github.com/YosysHQ/yosys) | 后续综合实验 | 查看上游 COPYING 及第三方组件声明 |
| [Gemmini](https://github.com/ucb-bar/gemmini) | 阵列、存储层次与完整 SoC 对照 | 查看上游 LICENSE；Chipyard 依赖需单独登记 |
| [PyTorch](https://github.com/pytorch/pytorch) | 自动求导和训练 | 查看上游 LICENSE 及第三方依赖 |
| [llm.c](https://github.com/karpathy/llm.c) | 阅读训练、推理的底层实现 | 阅读参考，不直接纳入 CUDA 作为必需依赖 |
| [MiniMind](https://github.com/jingyaogong/minimind) | 完整 LLM 训练、工具调用与 NPU 适配参考 | 固定提交根许可证 Apache-2.0；数据/权重单独核验；见 [来源记录](../models/minimind/source-lock.json) |

## 全开源的实际范围

- 必修实验不依赖付费 API、闭源预训练权重、商业 EDA 或专有板卡。
- GPU、FPGA、商业工具可以作为可选比较，但不得成为复现实验的唯一方式。
- 开源代码不代表训练数据自动开放；数据、权重、文档和硬件设计逐项记录许可。
- 不将“网上可下载”当作可再分发许可，不直接复制第三方教材全文。

## 每次引入的记录

在依赖或数据实际进入项目的同一变更中填写：名称、原始 URL、不可变提交/版本、下载内容 SHA-256、许可证、NOTICE、用途、本地修改、获取命令。未核验状态必须明确写出，不能填入猜测的版本或许可证。

首个训练集优先使用项目原创的简单任务与解释文本；开放语料在来源与许可核验完成后再添加。训练数据应先按文档分组切分，再生成窗口，避免相邻窗口泄漏到验证集。

## 参考读物与配套资料

[CSAPP《深入理解计算机系统》](https://csapp.cs.cmu.edu/3e/) 作为系统基础参考，已建立 [12 章知识映射与原创实验计划](CSAPP_FOUNDATIONS.md)。书籍并非本项目的开源组件；官方自学实验、示例及配套资料也应按各自条款核验。当前只提供链接和原创规划，不收入原书全文、扫描件、题库或官方答案，不将仓库 MIT 许可用于这些外部材料。

[Understanding Deep Learning](https://mitpress.mit.edu/9780262048644/understanding-deep-learning/) 作为模型理论参考，已建立 [21 章及附录映射](UDL_FOUNDATIONS.md)。出版社开放获取版标注 CC BY-NC-ND，官方资源仓库的[根许可证](https://github.com/udlbook/udlbook/blob/main/LICENSE)为 CC BY-NC-ND 4.0。本轮只加入原创学习组织、实验设计和链接；不收入或改编发布书稿、插图与官方 notebooks，不把可免费阅读视为 MIT 开源依赖。未来复用代码时逐文件核验许可。
