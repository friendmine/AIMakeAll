# 实验 17 · 在 QEMU 与 PicoRV32 上执行两层语言模型

同一个 ELF 接收输入和后端编号，固件执行嵌入、两层多头注意力、KV 更新、九个线性层、反量化和下一字节选择。分别跑 QEMU 和 PicoRV32 的纯 CPU / NPU 路径，串口在测量区间之后输出。

## 运行

从仓库根目录执行 `make lab17`。实验 15 环境、RV32IM 裸机工具链与项目版 RISC-V QEMU。 [环境与完整复现顺序](../../docs/EXPERIMENTS_09_23.md#复现环境)

## 交付与验收

四条路径的 768 个输出分数位模式、整数累积摘要和三个生成字节相同；与独立 PyTorch 参考的最大误差小于 0.0001。逐步核对实际 RTL 命令数。

提示 Th 均续写为 e、空格、a。纯 CPU 三步为 8,348,227 / 4,829,441 / 5,138,218 拍，NPU 为 6,929,091 / 3,961,777 / 4,270,426 拍。提示词处理包括给出首字节，静态模型映像加载在计时区间之外。

[本机已验证的报告](verified-run.json) · 新运行的报告位于 `build/language-soc/48-5468/report.json`。

## 迁移练习

换一个两字节提示，逐步对照 logits、整数摘要、下一字节及 MMIO 轨迹。

## 快速整机回归

`make language-ci` 使用仓库内冻结的实验 15 量化包，在本机从当前 C 和 RTL 源码重建固件与电路，无需 PyTorch、QEMU 或重新训练。两条路径实际处理 `Th`，每次比较 768 个分数与宿主参考、三个整数摘要和三个输出字节；CPU 命令数为零，NPU 三步为 304 / 184 / 184。完整的训练、重新导出及 QEMU 四路径对照仍用 `make lab17`。完成实验 15 后可用 `python3 labs/17-language-soc/freeze_ci.py` 重建小型回归输入。[工作流](../../.github/workflows/ci.yml) · [xPack 工具链版本与校验值](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/blob/v15.2.0-1.1/package.json)
