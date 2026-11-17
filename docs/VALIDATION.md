# 初始基线验证记录

日期：2026-11-17（Asia/Shanghai）。本地环境：macOS，Python 3.11.7，Verilator 5.044，系统 C++ 编译器。

| 命令/检查 | 结果 | 覆盖范围 |
| --- | --- | --- |
| `make test` | PASS，4 个测试 | 固定矩阵、65,536 对 INT8 乘积、INT32 溢出、非法输入 |
| `make demo` | PASS | 输出 `[[11, -15], [7, 8]]` |
| `make rtl-test` | PASS | 每个 INT8 输入对的累加结果、enable 保持、clear 优先级、异步复位与 INT32 回绕 |
| 本地 Markdown 相对链接 | PASS | 所有链接目标存在 |

GitHub CI 配置已提供，但尚未在远程执行。完整 CPU 集成、矩阵 NPU、QEMU 设备、模型训练与 Agent 均未实现或验证。这里的结果不包含任何性能加速结论。

## 本地 EDA 接入审计（2026-11-17）

- `make eda-doctor` 实际执行：26 个工具条目中，22 个版本查询成功；Netgen、KLayout 两项确认文件存在但未执行；两种 RISC-V QEMU 可执行文件未在检查位置找到。
- 记录 3 个 Python 环境的包元数据、14 份锁文件/环境入口的哈希、9 份历史结果摘要。快照见 [环境记录](environment/local-eda-2026-11-17.json)。这些不是外部流程重验。
- `make test demo` 通过：总计 8 个测试，新增环境检查的路径空格、缺失目录、候选歧义、未完成状态及损坏 JSON 的处理验证。
- 文档本地相对链接及 `git diff --check` 通过。
- 未修改外部 `asic-lab`，未安装或升级软件，未重跑大型表征；原有 RTL 本次未修改，因此不重复编译 RTL。
