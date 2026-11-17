# 从零 LLM（待实现）

主线不加载预训练权重。使用 PyTorch 自动求导，但自己实现数据流水线、模型层、训练与生成逻辑。先训练教学模型，再扩大规模。

建议起始配置：byte tokenizer（256 字节 token，额外特殊 token 单独定义）、上下文 128、4 层、hidden size 128、4 个 attention head、MLP hidden size 512。实际参数量由实现统计；这些配置尚未训练验证。byte tokenizer 对中文通常需要多个 token，不能把 tokens/s 直接解释为汉字/s。

训练顺序：bigram 基线 → 因果 Transformer → 验证集评估 → KV cache 推理 → INT8 导出 → NPU 线性层替换。首版在宿主机训练，教学 NPU 只做推理。

每次实验保存数据许可与哈希、文档级切分规则、随机种子、完整配置、依赖版本、参数量、训练/验证损失、困惑度和生成样例。量化先比较单层误差，再比较全模型 logits 与验证困惑度。详见 [M3 验收](../docs/ROADMAP.md)。

第一套原创小语料用于验证训练过程；工具调用能力需要后续专门数据与评测。能够生成文本不等于能够稳定完成 Agent 任务。
