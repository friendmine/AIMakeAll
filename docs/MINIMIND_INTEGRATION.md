# MiniMind：从零 LLM、NPU 部署与 Agent 的学习参考

更新日期：2026-11-17。参考项目：[jingyaogong/minimind](https://github.com/jingyaogong/minimind)。本次固定审阅提交为 **`233d00fa068ec2b8c0d4f07b703934d6391a5a73`**，不将不断变化的 `master` 当作实验版本。

**定位：MiniMind 作为 AIMakeAll 的完整模型训练参考线，连接模型阶段与 Agent 阶段。** 原有自写小模型课程继续承担数学、算子与硬件映射教学；MiniMind 提供更完整的模型、训练与工具调用实践。当前完成的是源码审阅、来源登记和接入设计，尚未安装其依赖、训练模型或接通 NPU。

## 1. 为什么加入这个项目

MiniMind 当前主线为 MiniMind3：Dense 约 64M 参数，也有 MoE 版本；仓库提供预训练、SFT、LoRA、偏好优化和工具调用相关训练代码。旧资料中的 26M MiniMind2-small 属于其他版本，不能把旧配置、权重和新 tokenizer 混用。上游所述“两小时”具体指单张 NVIDIA 3090 的一次 SFT epoch，并非在本机完成从零预训练、对齐和评测的总时间。[固定版本说明](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/README.md)

| AIMakeAll 目标 | MiniMind 提供的参考 | 本项目仍需完成 |
| --- | --- | --- |
| RISC-V + NPU | 真实线性层形状和存储需求 | 阵列、片上存储、总线、驱动与硬件验证 |
| QEMU Simulator | 可以部署的模型计算图 | RISC-V guest 运行时、设备模型及算子分派 |
| 从零 LLM | 模型结构、tokenizer、预训练与 SFT 流程 | 本机复现、合法数据与独立评测、INT8 导出 |
| Agent | 对话模板、工具调用、Agent RL 示例 | 项目工具实现、执行边界、独立任务集及 NPU 后端 |

采用两条互补学习线：先用自写的 1M–10M 级模型理解完整过程；再读 MiniMind，复现缩小配置，逐步推进默认 Dense 模型。MoE、强化学习和外部奖励模型放到后续选修。

## 2. 源码阅读顺序

阅读时对照 [Understanding Deep Learning 模块](UDL_FOUNDATIONS.md)：UDL04/UDL11/UDL12 支撑模型结构，UDL05 支撑标签与损失，UDL06/UDL07 支撑优化与初始化，UDL08/UDL09 支撑评估。具体的 RoPE、GQA、RMSNorm、门控 MLP 及训练算法继续以固定源码为准。

以下路径均相对于固定版本的上游仓库。来源记录包含本次审阅文件的 URL、字节数和 SHA-256，见 [source-lock.json](../models/minimind/source-lock.json)。

| 顺序 | 上游文件 | 学习任务与交付 |
| --- | --- | --- |
| 1 | `model/model_minimind.py` | 画出一层计算图，标注张量维度，列出需要加速的线性层 |
| 2 | `trainer/train_tokenizer.py`、`model/tokenizer_config.json` | 理解 BPE/ByteLevel、特殊标记和对话模板；比较基础课程 byte tokenizer |
| 3 | `dataset/lm_dataset.py` | 跟踪文本到 token、padding、标签和 SFT loss mask；检查实际参与损失的 token |
| 4 | `trainer/train_pretrain.py`、`trainer/trainer_utils.py` | 理解随机初始化、学习率、累积梯度、裁剪、保存与恢复 |
| 5 | `trainer/train_full_sft.py` | 理解从自己训练的预训练权重继续学习对话格式 |
| 6 | `scripts/convert_model.py` | 对照模型配置、参数名称和权重共享；区分格式转换与 INT8 量化 |
| 7 | `scripts/serve_openai_api.py`、`scripts/eval_toolcall.py` | 阅读服务协议与工具调用评估，先设计离线测试 |
| 8 | `trainer/train_agent.py`、`trainer/rollout_engine.py` | 分析多轮工具交互、奖励与 rollout；评估额外模型和运行后端依赖 |

这些是阅读与实验目标，不是已经完成的复现结果。完整上游源码仍在上游；本仓库未复制其实现。

## 3. 模型结构与资源预算

固定版本默认 Dense 配置为：8 层、hidden size 768、8 个 Q head、4 个 KV head、head dimension 96、词表 6400、MLP 中间维度 2432。结构包含 RMSNorm、Q/K 归一化、RoPE、GQA、SiLU 门控 MLP，以及共享 embedding / lm_head 权重。[模型源码](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/model/model_minimind.py)

从这些维度推导，共享权重只计一次，默认 Dense 参数量为 **63,912,192**。这是静态结构计算，尚未实例化模型实测；推导记录见 [dense-budget.json](../models/minimind/dense-budget.json)。

| 项目 | 静态估计 | 边界 |
| --- | --- | --- |
| 全参数 FP32 存储 | 约 243.81 MiB | 不含激活、优化器、运行时和临时空间 |
| 全参数 FP16 存储 | 约 121.90 MiB | 不代表本机 FP16 训练已验证 |
| 每参数 1 byte 的理论存储 | 约 60.95 MiB | 不是实际混合精度文件大小；未计 scale、对齐和保留浮点的参数 |
| batch=1、上下文 512、FP16 KV cache | 6 MiB | 仅未重复展开的 K/V 存储，未计注意力工作区；FP32 为 12 MiB |

KV cache 公式为 `2 × layers × batch × sequence × KV_heads × head_dim × bytes_per_element`。共享 embedding/lm_head 在导出时要保留别名关系；若转换为不同精度或布局而复制，真实存储会增加。

因此，已有 16 byte 教学 SRAM 适合解释存储单元，不能作为完整模型存储。需要分层设计外部 RAM、片上 tile buffer、权重分块和带宽预算；即使只有约 61 MiB 的理论 INT8 权重，也远超该宏容量。

## 4. 本机依赖与复现方式

本次只检查了当前 Python 包元数据：Python 3.11.7 中有 PyTorch 2.14.1、NumPy 2.4.2；未找到 `transformers`、`tokenizers`、`datasets`。已有包元数据不等于 MiniMind 能运行。

上游 `requirements.txt` 固定了 `transformers==4.57.6`、`datasets==3.6.0`、`numpy==1.26.4` 等版本，而 `torch==2.6.0` 仅为注释；它也包含 Web、日志、数据处理和其他训练阶段的依赖。因此该文件既不是本机已验收环境，也不是包含所有间接依赖的完整锁文件。[上游依赖](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/requirements.txt)

| 环境层 | 建议范围 | 验收 |
| --- | --- | --- |
| 最小模型阅读 / CPU | PyTorch、Transformers 及必要间接依赖 | 导入、缩小模型 forward/backward、保存加载 |
| 预训练 / SFT | 加 Tokenizers、Datasets、NumPy 等实际导入依赖 | 数据样例、loss mask、有限步训练、恢复 |
| 服务 / UI | 按需加入 API 服务和界面依赖 | 本地协议及输出格式测试 |
| Agent RL / 扩展 | 审核 reward model、rollout 后端与额外库 | 独立评测后再启用 |

为 MiniMind 新建专用虚拟环境，保留 EDA、OpenRAM 和当前项目环境。先解析依赖并保存安装报告，再锁定平台、Python、直接/间接依赖和下载哈希。不得把当前 NumPy 降级视为整个工作区的默认操作。

在所审阅的预训练脚本中，默认设备为 CUDA 或 CPU，混合精度和分布式逻辑主要按 CUDA 编写；未自动选择 MPS。**先做 CPU 小规模验证，再单独测试 MPS**，不能假定只传 `--device mps` 就已适配。检查随机数、dtype、梯度缩放、算子支持、缓存和保存加载行为。[训练脚本](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/trainer/train_pretrain.py)

CPU 首次试跑的建议参数是 hidden size 128、4 层、序列 128、batch 1、num_workers 0、MoE 关闭、torch.compile 关闭。先构造极小的原创数据集，验证有限更新步骤。此配置是本项目建议，未执行，不代表能训练出实用聊天能力。

从随机权重训练时，明确指定 `from_weight=none`、关闭自动恢复，并使用独立输出目录。SFT 再加载自己生成的 pretrain 权重。复用上游 tokenizer 与复用预训练模型权重是两件事；若另训 tokenizer，必须同步配置、词表哈希与模型权重，不能混用。

## 5. 数据与许可证

该固定提交的仓库根许可证为 **Apache-2.0**；本项目 MIT 许可证不覆盖其源码。当前只新增原创说明和来源元数据，未把上游源码、权重或数据收入 Git。将来复制或修改实现时，保留上游许可证、适用的版权/归属声明，标明修改，并检查对应组件的额外声明。[固定版本许可证](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/LICENSE)

数据和权重分别核验来源与许可，不根据代码仓库许可证推断。首批练习使用原创短文本；正式训练前建立数据清单，记录来源、许可、版本、哈希、处理步骤、切分规则及适用限制。蒸馏或外部奖励模型也单独登记，不作为“完全从随机权重训练”的必需条件。

阅读数据加载器时重点检查：预训练输入为每行含 `text` 的 JSON；SFT 使用 conversations，并屏蔽非目标位置的损失。正式数据先按文档/来源去重和切分，再产生训练窗口；工具任务还要按模板或任务族隔离测试集。[数据实现](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/dataset/lm_dataset.py)

## 6. 映射到 AIMakeAll NPU

新增 [AI 编译课程](AI_COMPILATION.md)，承接固定源码中的线性层到布局、量化、分块及执行计划；先验证单 Linear，再扩展模型。[ENG01–ENG03](ENGINEERING_BRIDGES.md) 分别补数值、数据训练和性能验证。当前不存在已验证的 MiniMind 自动导出/NPU 编译后端。

首版目标是 **Dense 模型的 INT8 线性层推理**。训练仍在宿主机进行。上游的模型格式转换不能替代我们的量化导出器、C 运行时和设备驱动。[上游转换实现](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/scripts/convert_model.py)

| 计算 | 默认配置下的投影维度 | 首版执行位置 |
| --- | --- | --- |
| Q / O 投影 | 768 → 768 | NPU GEMM 候选 |
| K / V 投影 | 768 → 384 | NPU GEMM 候选 |
| gate / up 投影 | 768 → 2432 | NPU GEMM 候选 |
| down 投影 | 2432 → 768 | NPU GEMM 候选 |
| lm_head | 768 → 6400 | NPU GEMM 候选；处理与 embedding 的共享权重 |
| RMSNorm、Q/K norm、RoPE、SiLU、残差 | 非线性或逐元素运算 | CPU 浮点 |
| QKᵀ、Softmax、AV | 随上下文变化，含动态张量 | 首版 CPU；后续独立评估注意力量化 |
| tokenizer、embedding gather、采样、KV 管理 | 字节/索引/状态处理 | CPU |

适配链路：`PyTorch FP32 基线 → 量化数值参考 → 权重导出 → C CPU 后端 → QEMU NPU → RTL 对照`。每一步先比较结果，再测性能；不能跳过中间层直接用生成文本判断正确性。

关键实现约束：

1. PyTorch 权重为 W[N,K]，设备 B 为行优先 B[K,N]；导出器显式转置，记录量化 scale 和布局。
2. 现有 [NPU v0 草案](../specs/npu-v0.md) 每个维度上限为 256，而上述多数维度超过限制；必须按 M/N/K 分块并处理尾块。
3. 设备每次 GEMM 从零累加，不能假定跨 K 分块自动累加。运行时先合并 INT32 partial sums，再统一反量化；若每块用不同 scale，则需要单独定义合并语义。初版可在 CPU 合并，后续扩展设备 ABI。
4. 激活与权重先采用零点为零的对称量化，定义校准方式；参考浮点 `Y ≈ C × s_x × s_w[n]`，不要把 dtype 转换当成量化。
5. Prefill 的 M 可较大，decode 通常 M=1；对两者分别测 NPU 利用率、权重搬运、CPU 回退和总耗时。
6. 量化质量使用独立数据上的 logits 误差、困惑度和任务成功率；初始困惑度相对增幅目标沿用 M3 的 10%，超标就记录失败。

这些是本项目适配设计，尚无 MiniMind→NPU 实现或加速结果。QEMU 模拟路径的耗时也不代表真实芯片速度。

## 7. 连接到 Agent

MiniMind 的对话模板包含工具调用结构；本次审阅的 `train_agent.py` 还包含多轮 rollout 和奖励逻辑。示例天气、时间、汇率等工具使用固定模拟数据，不是实时服务。默认配置还涉及额外奖励模型，不能不加区分地作为纯自训练闭环。[Agent 训练实现](https://github.com/jingyaogong/minimind/blob/233d00fa068ec2b8c0d4f07b703934d6391a5a73/trainer/train_agent.py)

本项目先完成受限工具 SFT 与执行循环：

- 将上游工具调用格式转换成 AIMakeAll 内部协议，校验工具名、参数、返回消息和终止状态。
- 提供计算器、限定目录资料检索和实验结果查询，不把模拟天气或时间当作真实查询。
- 规则策略、模型策略、预训练权重来源和推理后端分别标记。
- 用固定的独立任务集报告合法调用率、成功率、步数、模型耗时和总耗时，再决定是否需要 Agent RL。

NPU 主要降低模型推理部分的耗时；文件检索、工具执行和校验仍在 CPU。最终比较同一模型、同一任务在 CPU 与 NPU 路径上的质量及延迟。

## 8. 分阶段验收

| 阶段 | 交付与通过条件 | 当前状态 |
| --- | --- | --- |
| MM0 来源与阅读 | 固定提交、源码索引、依赖分析、算子映射 | 本次完成 |
| MM1 CPU 小模型 | 独立环境、有限步训练、保存加载、独立验证损失 | 待实现 |
| MM2 预训练与 SFT | 从随机权重出发，保留数据/配置/曲线及任务评测 | 待实现 |
| MM3 量化与导出 | 单层与整模型对照，布局/scale/共享权重检查 | 待实现 |
| MM4 NPU 执行 | C/QEMU/RTL 数值对照，prefill/decode 分开报告 | 待实现 |
| MM5 Agent | 工具协议、错误处理、独立任务成功率和延迟 | 待实现 |

下一步优先完成 MM1，同时继续原有硬件主线。仅阅读上游代码不等于从零训练完成；加载上游成品权重的演示应作为单独的对照实验登记。
