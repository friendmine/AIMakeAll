# 推理运行时

计划提供统一 GEMM 分派接口，对接 C 标量参考、RISC-V MMIO 和未来优化后端。每个后端公开支持的维度、数据类型和布局；不支持的算子显式回退 CPU，并统计回退次数。

第一批工作：整数 GEMM、权重加载、线性层、FP32 归一化与 Softmax。内存分配先采用静态预算，设备返回错误不能静默伪装为成功。

新增 [AI 编译与执行计划路线](../docs/AI_COMPILATION.md)：有限图经过检查、布局/量化、分块和内存规划后交给 C 运行时。运行时负责实际地址绑定、动态输入处理、同步提交、K 部分结果合并及 CPU 后处理；不得把设备不支持的累加、bias 或中断隐含在 GEMM 中。[实验 01](../labs/01-linear257/README.md)已执行固定形状的分块计划，并在裸机 C 中合并和缩放。通用模型包解析与算子回退为后续交付。

[算法](../docs/ALGORITHMS_FOUNDATIONS.md) 补任务依赖与队列，[OSTEP](../docs/OSTEP_FOUNDATIONS.md) 补 arena、并发和生命周期；[工程专项](../docs/ENGINEERING_BRIDGES.md) 规定数值与性能验证。

导出格式需包含 magic、格式版本、字节序、模型配置、张量名称/形状/类型/偏移/长度、量化 scale 和内容校验和。加载器在分配和访问前校验所有边界；版本未定前不要生成长期兼容的模型文件。

以 [SW-E1–E6](../docs/SYSTEMATIC_VERIFICATION.md) 深化 C 数值语义、坏包校验、程序检测、缓冲区所有权、可复现构建和跨层回归。首版限定形状、总字节和张量数；先在宿主测参考/加载器，再分别验收 guest 后端。超时不等于设备已停止访问缓冲区，回收必须有完成或静止证据。实验仍待实现。

[ARCH-E1–E6](../docs/ARCHITECTURE.md) 为分块与内存计划提供访问账本、容量/bank 约束及可见性实验；CPU Cache、局部 scratchpad 与 LLM KV Cache 分别建模。缓存一致性、异步重叠与 CXL 访问均须后端显式支持，不由编译计划假定。

与 [NPU 规范](../specs/npu-v0.md) 对齐，并将 CPU 标量、设备结果、模型误差与性能分别验收。

硬件故障扩展参考 [RAS-E4/E6](../docs/ARCHITECTURE.md#领域-04-与-17-深化硬件数据完整性与故障处置)：先在独立包装中区分已纠正事件、不可纠正错误和结果有效性；UE 后不得发布部分结果为成功，恢复需新任务及明确的重新初始化/装载。现有 v0 没有 ECC 上报 ABI，未来设备/驱动接入须另行设计并验证，不能直接复用 START 前参数错误或假定输出可回滚。该扩展不阻塞首个正常 Linear。

性能基准按 [PERF-E1–E6](../docs/ENGINEERING_BRIDGES.md) 从正确 C 标量到分块、SIMD 和线程逐项建立，宿主与 guest 的能力和测量分别记录；内核时间与含加载/打包/提交/回退的端到端时间都保留。[MEM-E1/E6](../docs/ARCHITECTURE.md) 提供事务和排队分析，[PPA-E](../docs/DIGITAL_DESIGN_TIMING.md) 的目标设计能耗估算另报，不从 QEMU 宿主耗时或用电外推。全部待实现，初版仍单请求同步执行。

后续 [LFS/Linux 扩展](../docs/LFS_FOUNDATIONS.md) 增加 Linux 设备后端：通过驱动接口提交 GEMM，由内核管理缓冲区、地址与完成通知；不在普通进程中直接复用裸机 MMIO 指针。Linux C 运行时、模型文件加载与服务生命周期分别验收，当前仅为设计。

互连扩展分三条：通过 [IO05](../docs/PCIE_IO_FOUNDATIONS.md) 新增独立 PCIe 设备后端；通过 [NET03–NET05](../docs/NETWORKING_FOUNDATIONS.md) 在运行时外层提供有界 RPC 服务；通过 [CX05](../docs/CXL_MEMORY_FOUNDATIONS.md) 探索权重/KV 的内存放置。网络消息和编译计划均不携带未经绑定的设备地址；CXL 内存不自动成为 NPU 可寻址内存，必要暂存与搬运计入开销。所有新后端与放置策略仍待实现。

## 生命周期 认证与模型更新

[LIFE/TRUST/SHIFT](../docs/CHIP_AI_COMPLETENESS.md#六项跨层补强) 规划平台静止/恢复、认证后的包校验、防回滚与模型版本更新。先独立模型再接已验后端；已验证字节与加载字节一致，认证不代替格式/内存/能力检查。所有新增节点待实现，沿用 NPU v0 的轮询与 reset 合同。
