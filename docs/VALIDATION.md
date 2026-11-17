# 初始基线验证记录

日期：2026-11-17（Asia/Shanghai）。本地环境：macOS，Python 3.11.7，Verilator 5.044，系统 C++ 编译器。

| 命令/检查 | 结果 | 覆盖范围 |
| --- | --- | --- |
| `make test` | PASS，4 个测试 | 固定矩阵、65,536 对 INT8 乘积、INT32 溢出、非法输入 |
| `make demo` | PASS | 输出 `[[11, -15], [7, 8]]` |
| `make rtl-test` | PASS | 每个 INT8 输入对的累加结果、enable 保持、clear 优先级、异步复位与 INT32 回绕 |
| 本地 Markdown 相对链接 | PASS | 所有链接目标存在 |

GitHub CI 配置已提供，但尚未在远程执行。完整 CPU 集成、矩阵 NPU、QEMU 设备、模型训练与 Agent 均未实现或验证。这里的结果不包含任何性能加速结论。
