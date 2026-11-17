# MiniMind 参考模块

这里登记 MiniMind 在 AIMakeAll 中的学习与适配方案。上游：[jingyaogong/minimind](https://github.com/jingyaogong/minimind)，固定审阅提交 `233d00fa068ec2b8c0d4f07b703934d6391a5a73`。

- [完整学习与接入文档](../../docs/MINIMIND_INTEGRATION.md)：源码路线、本机依赖、训练、INT8/NPU 映射与 Agent。
- [来源锁记录](source-lock.json)：16 份审阅文件的固定 URL 与 SHA-256；是来源元数据，不是依赖安装锁。
- [Dense 静态资源预算](dense-budget.json)：从配置推导参数与内存；尚未实例化模型实测。

当前没有引入上游源码、训练数据或模型权重，没有安装依赖或执行训练。审阅用下载文件放在被 Git 忽略的 `build/minimind-review/`，不属于发布内容。

学习时先完成原有 [INT8 入门实验](../../labs/00-int8-matmul/README.md)，再按 MM0–MM5 推进。使用 MiniMind 源码时沿用其 Apache-2.0 许可证；数据、权重与额外模型分别核验。
