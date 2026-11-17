# 硬件主线

当前只有 `rtl/mac_int8.sv`：带 enable 和同步 clear 的有符号 INT8 乘加单元，异步低有效复位，32 位回绕累加。这是 NPU 的基本组件，并非完整 NPU 或 SoC。

运行 `make rtl-test`。下一步依次实现 4×4 阵列、局部存储、分块控制、MMIO 外设以及 Ibex 集成。对照 [算子规范](../specs/npu-v0.md) 和 [里程碑 M1](../docs/ROADMAP.md)。

外部 CPU 源码尚未引入；引入时固定提交并保存许可声明。首版 CPU 裸机运行，不能据此声称支持 Linux。

按 [仿真优先与数字电路交付原则](../docs/SIMULATION_FIRST.md)，后续硬件交付包括可综合 RTL、独立测试模型、波形和综合报告；不以 FPGA 或流片为核心验收门槛。网络增加 MAC/FIFO/CRC 教学数据路径，PCIe 增加 TLP/BAR/NPU 桥子集，CXL 增加地址译码/队列/存储子模块。高速 PHY/SerDes 以接口模型替代，教学子集不等于完整标准控制器。数字 RTL 到 GDS 是独立可选扩展，仍可在电脑内完成。

已有外部 `~/asic-lab` 提供仿真、形式验证、RTL 到 GDS、SRAM 和数模实验基础。本项目已纳入其 [软件依赖与接入分析](../docs/LOCAL_EDA_ENVIRONMENT.md)，可用 `make eda-doctor` 盘点。原实验尚未迁移至仓库；已有 PicoRV32 可作为联调候选，Ibex 主线仍保留。新 SRAM 的 RC 多工况验收尚未完成，禁止直接沿用旧时序库。
