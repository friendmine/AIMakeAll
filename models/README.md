# 从零 LLM（待实现）

主线不加载预训练权重。使用 PyTorch 自动求导，但自己实现数据流水线、模型层、训练与生成逻辑。先训练教学模型，再扩大规模。

建议起始配置：byte tokenizer（256 字节 token，额外特殊 token 单独定义）、上下文 128、4 层、hidden size 128、4 个 attention head、MLP hidden size 512。实际参数量由实现统计；这些配置尚未训练验证。byte tokenizer 对中文通常需要多个 token，不能把 tokens/s 直接解释为汉字/s。

训练顺序：bigram 基线 → 因果 Transformer → 验证集评估 → KV cache 推理 → INT8 导出 → NPU 线性层替换。首版在宿主机训练，教学 NPU 只做推理。

每次实验保存数据许可与哈希、文档级切分规则、随机种子、完整配置、依赖版本、参数量、训练/验证损失、困惑度和生成样例。量化先比较单层误差，再比较全模型 logits 与验证困惑度。详见 [M3 验收](../docs/ROADMAP.md)。

第一套原创小语料用于验证训练过程；工具调用能力需要后续专门数据与评测。能够生成文本不等于能够稳定完成 Agent 任务。

数据去重/切分、检查点恢复与数值误差纳入 [ENG01/ENG02](../docs/ENGINEERING_BRIDGES.md)。模型部署增加 [AI 编译路线](../docs/AI_COMPILATION.md)，先用单 Linear 验证图到计划的转换，再接完整模型；不把计划解释器可运行等同于训练或硬件部署完成。

## MiniMind 参考线

模型理论先读 [Understanding Deep Learning 项目映射](../docs/UDL_FOUNDATIONS.md)：损失、反向传播、优化与泛化 → 残差与注意力 → 自写模型与 MiniMind。数学附录按需补齐，广度选修不作为首版训练的前置门槛。

已加入 [MiniMind 参考模块](minimind/README.md)，固定审阅 MiniMind3 源码，提供预训练/SFT 学习路线、依赖分析、资源预算、INT8 NPU 映射与 Agent 接入方案。它与本项目自写基础模型课程并行：先理解小模型，再参考完整训练流程。当前仅完成文档与来源登记，尚未训练或部署。详见 [接入文档](../docs/MINIMIND_INTEGRATION.md)。
