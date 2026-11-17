# 推理运行时（待实现）

计划提供统一 GEMM 分派接口，对接 C 标量参考、RISC-V MMIO 和未来优化后端。每个后端公开支持的维度、数据类型和布局；不支持的算子显式回退 CPU，并统计回退次数。

第一批工作：整数 GEMM、权重加载、线性层、FP32 归一化与 Softmax。内存分配先采用静态预算，设备返回错误不能静默伪装为成功。

新增 [AI 编译与执行计划路线](../docs/AI_COMPILATION.md)：有限图经过检查、布局/量化、分块和内存规划后交给 C 运行时。运行时负责实际地址绑定、动态输入处理、同步提交、K 部分结果合并及 CPU 后处理；不得把设备不支持的累加、bias 或中断隐含在 GEMM 中。首项是单 Linear 的软件计划解释器，全部待实现。

[算法](../docs/ALGORITHMS_FOUNDATIONS.md) 补任务依赖与队列，[OSTEP](../docs/OSTEP_FOUNDATIONS.md) 补 arena、并发和生命周期；[工程专项](../docs/ENGINEERING_BRIDGES.md) 规定数值与性能验证。

导出格式需包含 magic、格式版本、字节序、模型配置、张量名称/形状/类型/偏移/长度、量化 scale 和内容校验和。加载器在分配和访问前校验所有边界；版本未定前不要生成长期兼容的模型文件。

与 [NPU 规范](../specs/npu-v0.md) 对齐，并将 CPU 标量、设备结果、模型误差与性能分别验收。

后续 [LFS/Linux 扩展](../docs/LFS_FOUNDATIONS.md) 增加 Linux 设备后端：通过驱动接口提交 GEMM，由内核管理缓冲区、地址与完成通知；不在普通进程中直接复用裸机 MMIO 指针。Linux C 运行时、模型文件加载与服务生命周期分别验收，当前仅为设计。

互连扩展分三条：通过 [IO05](../docs/PCIE_IO_FOUNDATIONS.md) 新增独立 PCIe 设备后端；通过 [NET03–NET05](../docs/NETWORKING_FOUNDATIONS.md) 在运行时外层提供有界 RPC 服务；通过 [CX05](../docs/CXL_MEMORY_FOUNDATIONS.md) 探索权重/KV 的内存放置。网络消息和编译计划均不携带未经绑定的设备地址；CXL 内存不自动成为 NPU 可寻址内存，必要暂存与搬运计入开销。所有新后端与放置策略仍待实现。
