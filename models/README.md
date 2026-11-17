# 从零 LLM（待实现）

主线不加载预训练权重。使用 PyTorch 自动求导，但自己实现数据流水线、模型层、训练与生成逻辑。先训练教学模型，再扩大规模。

建议起始配置：byte tokenizer（256 字节 token，额外特殊 token 单独定义）、上下文 128、4 层、hidden size 128、4 个 attention head、MLP hidden size 512。实际参数量由实现统计；这些配置尚未训练验证。byte tokenizer 对中文通常需要多个 token，不能把 tokens/s 直接解释为汉字/s。

训练顺序：bigram 基线 → 因果 Transformer → 验证集评估 → KV cache 推理 → INT8 导出 → NPU 线性层替换。首版在宿主机训练，教学 NPU 只做推理。

每次实验保存数据许可与哈希、文档级切分规则、随机种子、完整配置、依赖版本、参数量、训练/验证损失、困惑度和生成样例。量化先比较单层误差，再比较全模型 logits 与验证困惑度。详见 [M3 验收](../docs/ROADMAP.md)。

第一套原创小语料用于验证训练过程；工具调用能力需要后续专门数据与评测。能够生成文本不等于能够稳定完成 Agent 任务。

数据去重/切分、检查点恢复与数值误差纳入 [ENG01/ENG02](../docs/ENGINEERING_BRIDGES.md)。模型部署增加 [AI 编译路线](../docs/AI_COMPILATION.md)，先用单 Linear 验证图到计划的转换，再接完整模型；不把计划解释器可运行等同于训练或硬件部署完成。

[CLA/DLE/SCALE 全景扩展](../docs/CHIP_AI_COMPLETENESS.md) 补树/核/聚类、梯度与生成模型比较、分布式训练/推理；EMB 衔接视觉/音频与控制。先完成 DLE 小模型和 DEP 单 Linear，专题不全部前置于 LLM；新增实验均待实施。

## Build a Large Language Model (From Scratch) 参考线

更新：2026-11-17。将 Sebastian Raschka 的 *Build a Large Language Model (From Scratch)* 作为领域 10“从零 LLM”的逐步实现参考，连接已有领域 01/09/08/11/12，不新增一级目录或知识领域。依据 [Manning 书目](https://www.manning.com/books/build-a-large-language-model-from-scratch) 与 [官方代码仓库](https://github.com/rasbt/LLMs-from-scratch) 的七章及附录 A–E 建立下列映射。这里只完成资料核对与原创实验规划，未复现书中训练、下载数据/权重或引入上游源码。

三条参考线分工：UDL 解释模型、优化与泛化的原理；本书帮助逐层写出可检查的 GPT 风格模型；MiniMind 用于比较完整训练流程和不同结构。AIMakeAll 再承担量化、AI 编译、C 运行时、QEMU/NPU 与受限 Agent 集成。先做本书对应的小模型实验，再按需阅读 MiniMind，不要求先读完 UDL。

### 七章对应的项目实验

`LLMFS01–LLMFS07` 对应书中章节顺序；下表为项目原创实验与验收，不是官方练习答案。它们细化现有单元 08–15，不重复计算实现进度，全部待实现。

| 编号 / 章节主题 | 对应现有课程 | 项目实验与产物 | 验收依据 |
| --- | --- | --- | --- |
| LLMFS01 / LLM 与训练阶段 | UDL01、单元 08、ENG02 | 为预训练、分类微调、指令微调列出输入/目标/权重来源；绘制自己的数据到任务流程 | 随机初始化、训练后的模型、外部预训练权重分别标记；不把定义网络视为训练完成 |
| LLMFS02 / 文本与输入表示 | 单元 08、ENG02、MATH-E5 | 先用现有 byte tokenizer 方案实现编码、窗口、右移标签和 embedding；再做 BPE 对照 | 已知短序列可手算；先按文档去重/划分再切窗口；记录词表/特殊 token，测试边界和编码还原 |
| LLMFS03 / 注意力实现 | 单元 09、UDL12、MATH-E2/E3 | 从小矩阵 Q/K/V 到因果多头注意力，保存形状与中间结果 | 关闭 dropout 后修改未来 token 不影响之前 logits；有效行归一化正确，与独立小参考对照 |
| LLMFS04 / GPT 组装 | 单元 09/11、UDL11/12、ARCH-E1 | 组装 embedding、位置、归一化、残差、MLP 与输出头；输出参数/激活账本 | 形状和参数量由实现统计；eval 下保存加载前后输出一致；分清已训练能力与随机模型的可执行性 |
| LLMFS05 / 预训练与生成 | 单元 10/11、ENG02、SW-E5 | 自有小语料随机初始化训练，记录 token 损失、采样策略、checkpoint 与恢复；对照 bigram | 极小样本过拟合仅用于查错，泛化另看留出集；相同 tokenizer/划分比较基线，恢复记录优化器、步数、随机和数据位置 |
| LLMFS06 / 分类微调 | UDL02/08、M3 扩展 | 在自己训练的骨干上增加分类头，对比冻结骨干与全参数训练；制作原创、分组划分的标签集 | 不把分类准确率当生成质量；检查 padding/选取 token，报告混淆矩阵及类别分布；不阻塞生成主线 |
| LLMFS07 / 指令微调 | 单元 15、ENG04、STATE-E1–E6 | 自有指令数据 → 模板与 loss mask → SFT → 受限工具 JSON；保存模板外任务集 | 明确哪些 token 计入损失，padding 被屏蔽；指令质量、调用格式合法率与实际任务成功率分开，工具权限由程序验收 |

第 6 章对应分类分支，可与生成路线并行。第 7 章的项目工具调用实验是我们在指令微调基础上的扩展，不把书中指令模型等同于已经具备完整 Agent。

### 附录与上游扩展的使用方式

| 范围 | 项目用途与边界 |
| --- | --- |
| LLMFS-A / PyTorch 入门 | 张量、自动求导和训练基础；先做 CPU 的 forward/backward 小例，连接 MATH-E3；多 GPU 不是前置 |
| LLMFS-B / 参考资料 | 作为进一步阅读索引，按实际引用逐项登记来源，不导入整套外部材料 |
| LLMFS-C / 习题解答 | 仅链接官方自学入口；项目保持原创实验和独立验收，不复制答案 |
| LLMFS-D / 训练循环改进 | 随 ENG02 比较学习率调度、梯度裁剪与恢复；固定数据/预算做受控实验，记录失败配置 |
| LLMFS-E / LoRA | 作为 SFT 后的选修；核对可训练参数，并在 FP32 下比较显式低秩分支与合并权重的输出，量化后重新评估 |

上游仓库另有 KV cache、其他模型结构、DPO 等补充材料，它们不是原书七章新增章节，也不是本项目首版必修。当前只核对目录及部分入口，未全面审阅这些扩展。KV cache 仍接本项目单元 11，测试相同上下文/位置语义下缓存与非缓存路径的 logits；不直接用随机采样文本是否相同代替数值对照。

### 与 MiniMind、NPU 和 Agent 的连接

书中 [GPT 实现](https://github.com/rasbt/LLMs-from-scratch/blob/main/ch04/01_main-chapter-code/gpt.py) 的主干使用学习式位置 embedding、普通多头注意力、LayerNorm 和 GELU MLP。已固定审阅的 [MiniMind](../docs/MINIMIND_INTEGRATION.md) 则包含 RoPE、GQA、RMSNorm 和门控 MLP。可以逐项对照，但不能直接混用配置、tokenizer 或权重；采用本项目 byte 词表与缩小结构时，也不能直接加载 GPT-2 权重。

部署顺序保持为单 Linear → Q/K/V/O 投影和 MLP 线性层 → 模型推理。线性层经 [AI 编译](../docs/AI_COMPILATION.md) 的布局/量化/分块进入 [运行时](../runtime/README.md)；bias、LayerNorm、GELU、Softmax、embedding gather、位置处理与采样首版留 CPU。QKᵀ/AV 的动态注意力矩阵另行评估，不因它们也是矩阵乘法就默认已受支持。训练与 LoRA 更新仍在宿主完成，NPU v0 只承担已定义的整数推理算术。

第 7 章与 [上游扩展](https://github.com/rasbt/LLMs-from-scratch/blob/main/ch07/README.md) 可帮助理解指令数据和评估组织；本项目核心验收使用自有任务判据、必要的人工核查和程序执行结果，不依赖付费评判 API。模型回答、检索命中、工具安全和持久任务恢复各自验收。

### 开始实施的顺序与来源

1. 随数学基础完成 LLMFS-A、LLMFS02 的小张量/短序列实验；保留现有 byte tokenizer 与 bigram 起点。
2. 实现 LLMFS03/04 的小模型和因果性测试，再用 LLMFS05 验证有限步训练、保存恢复与留出评估；CPU 先验，MPS/CUDA 分别记录。
3. 用自训练权重做 LLMFS07；LLMFS06 与 LoRA 为后续分支。独立记录外部预训练权重的对照实验，不计作“从随机权重训练”。
4. 复用 G2 的单 Linear 导出与部署证据，再扩大到完整模型。硬件/QEMU 路线不等待完整模型训练。

资料来源为 [作者书页](https://sebastianraschka.com/llms-from-scratch/)、官方仓库章节索引以及 [第 5 章入口](https://github.com/rasbt/LLMs-from-scratch/blob/main/ch05/README.md)。这里的 `main` 链接是阅读入口，不是可复现实验锁定版本；首次运行或引入源码时须固定提交、文件哈希、依赖与平台。官方示例可用于常规电脑上的教学，但不据此推断完整预训练的时间、内存预算或聊天质量；本项目小配置也尚未运行。

官方根 [LICENSE.txt](https://github.com/rasbt/LLMs-from-scratch/blob/main/LICENSE.txt) 以 Apache-2.0 为基础，并在 Source 定义中明确排除相关书籍和图片；不将此声明推广为书稿、插图、数据和权重的统一授权。当前只保存原创映射和链接；复用具体代码时核对文件声明、保留适用许可与归属，并与仓库 MIT 原创内容区分。

## MiniMind 参考线

模型理论先读 [Understanding Deep Learning 项目映射](../docs/UDL_FOUNDATIONS.md)：损失、反向传播、优化与泛化 → 残差与注意力 → 自写模型与 MiniMind。数学附录按需补齐，广度选修不作为首版训练的前置门槛。

已加入 [MiniMind 参考模块](minimind/README.md)，固定审阅 MiniMind3 源码，提供预训练/SFT 学习路线、依赖分析、资源预算、INT8 NPU 映射与 Agent 接入方案。它与本项目自写基础模型课程并行：先理解小模型，再参考完整训练流程。当前仅完成文档与来源登记，尚未训练或部署。详见 [接入文档](../docs/MINIMIND_INTEGRATION.md)。
