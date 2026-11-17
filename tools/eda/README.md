# 本地 EDA 环境检查

此模块把现有 `~/asic-lab` 纳入 AIMakeAll 的依赖盘点，不复制工具、PDK 或仍在生成的 SRAM 产物。

```sh
make eda-doctor
# 或指定其他路径
python3 tools/eda/inspect_environment.py --asic-lab /path/to/asic-lab --output build/eda-environment.json
```

检查器只读取明确列出的路径、运行带 10 秒超时的版本查询，并记录锁文件/历史报告 SHA-256。不会执行外部环境脚本，不联网、不安装、不启动设计回归、不刷新外部报告。唯一写入是指定的 JSON 输出；默认 `build/` 已忽略。

返回状态含义：

- `version_ok`：版本命令成功，不代表功能测试通过。
- `file_present_not_executed`：工具文件存在，本次没有启动 GUI 或 LVS。
- `not_found_in_checked_locations`：当前 PATH 和指定候选路径未找到，不代表全磁盘绝对没有。
- `ambiguous_requires_selection`：同类 Nix 版本出现多个候选，不自动选取。
- `recorded_not_rerun`：读取了已有报告，未重跑其中的实验。

脚本正常退出仅表示盘点完成，缺失工具会留在 JSON 中，不能把退出码 0 当作“环境全部就绪”。Nix 路径模式对应当前已知版本；换机器/升级后需要审查并更新，不是通用安装器。

完整分析与分层依赖见 [本地芯片开发环境](../../docs/LOCAL_EDA_ENVIRONMENT.md)，本次固定快照见 [2026-11-17](../../docs/environment/local-eda-2026-11-17.json)。快照只包含元数据与状态摘要，原始证据仍位于外部实验目录。
