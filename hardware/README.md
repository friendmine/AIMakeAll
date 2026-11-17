# 硬件主线

当前只有 `rtl/mac_int8.sv`：带 enable 和同步 clear 的有符号 INT8 乘加单元，异步低有效复位，32 位回绕累加。这是 NPU 的基本组件，并非完整 NPU 或 SoC。

运行 `make rtl-test`。下一步依次实现 4×4 阵列、局部存储、分块控制、MMIO 外设以及 Ibex 集成。对照 [算子规范](../specs/npu-v0.md) 和 [里程碑 M1](../docs/ROADMAP.md)。

并行建立 [DD03 同步 FIFO](../docs/DIGITAL_DESIGN_TIMING.md) 作为数字设计入门，按 [DV](../docs/SYSTEMATIC_VERIFICATION.md) 补独立参考、断言、覆盖/故障与形式性质，再按 [SIM](../docs/SIMULATION_CREDIBILITY.md) 对照周期模型和轨迹。新 FIFO 的同步复位契约不改变现有 MAC；DD06 异步 FIFO 和目标库 STA 按需求后置。新增实验当前只有设计，无 RTL/证明/综合网表产物。

外部 CPU 源码尚未引入；引入时固定提交并保存许可声明。首版 CPU 裸机运行，不能据此声称支持 Linux。

新增 [ARITH-E1–E6 算术电路](../docs/DIGITAL_DESIGN_TIMING.md#dd01dd02dd07-深化计算机算术与算术电路结构)：位宽/加法器 → 迭代/并行乘法 → 定点舍入与 MAC 结构对照；候选先独立验证，再决定是否接阵列。[RAS-E1–E6 数据完整性](../docs/ARCHITECTURE.md#领域-04-与-17-深化硬件数据完整性与故障处置) 从奇偶校验、SECDED 到受保护存储、错误上报和 GEMM 故障处置，先用行为 RAM 与 RTL 包装。两组均待实现，ECC 不阻塞首个正常 GEMM，现有 MAC 复位与 v0 ABI 保持不变。

深化实验增加 [MEM-E1–E6](../docs/ARCHITECTURE.md)：先事务账本与两来源单端口仲裁 RTL，再独立研究 DRAM 调度和小 NoC 模型；不要求首版接完整 DRAM/NoC。[PPA-E1–E6](../docs/DIGITAL_DESIGN_TIMING.md) 随 DD07 比较相同功能下的面积/时序，适用库和活动证据具备后再分析任务能耗。模型、可综合电路、门级/物理估算分别验收，新增实验均待实现。

按 [仿真优先与数字电路交付原则](../docs/SIMULATION_FIRST.md)，后续硬件交付包括可综合 RTL、独立测试模型、波形和综合报告；不以 FPGA 或流片为核心验收门槛。网络增加 MAC/FIFO/CRC 教学数据路径，PCIe 增加 TLP/BAR/NPU 桥子集，CXL 增加地址译码/队列/存储子模块。高速 PHY/SerDes 以接口模型替代，教学子集不等于完整标准控制器。数字 RTL 到 GDS 是独立可选扩展，仍可在电脑内完成。

已有外部 `~/asic-lab` 提供仿真、形式验证、RTL 到 GDS、SRAM 和数模实验基础。本项目已纳入其 [软件依赖与接入分析](../docs/LOCAL_EDA_ENVIRONMENT.md)，可用 `make eda-doctor` 盘点。原实验尚未迁移至仓库；已有 PicoRV32 可作为联调候选，Ibex 主线仍保留。新 SRAM 的 RC 多工况验收尚未完成，禁止直接沿用旧时序库。
