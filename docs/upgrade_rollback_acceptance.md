# Gate 4：Windows 升级与回滚验收

Gate 4 验证真实 NSIS 安装器的生命周期行为。它不使用源码运行、不把同版本重装称为升级，也不把
Advanced AI 内部组件指针切换冒充桌面应用升级。

## 候选要求

准备两套由 Windows Release Smoke 构建的候选：

- baseline：较低的三段式应用版本，例如 `0.9.0`；
- candidate：较高的三段式应用版本，例如 `1.0.0`；
- 两者必须来自不同 commit，具有不同安装器 SHA-256；
- `gate1-build-metadata.json` 必须包含 `app_version`、commit、workflow run ID、安装器名称和 SHA-256。

同为 `1.0.0` 的两个 RC 构建只能证明重装或替换，不能使本 Gate PASS。正式回滚遵循当前
`allowDowngrades: false` 策略：旧安装器不能直接覆盖较新版本；需要先卸载 candidate，再安装
baseline，并确认用户数据仍然保留。

## 自动验收内容

`scripts/run_windows_upgrade_acceptance.py` 按顺序执行：

1. 校验两套候选的版本、commit、run ID、文件名和 SHA-256；
2. 安装 baseline，验证 Desktop/Core Runtime/Core Models 布局并执行 Core smoke；
3. 在保留用户数据标记的情况下原位安装 candidate；
4. 确认关键安装载荷确实改变，candidate 的 Core 仍然 Ready；
5. 尝试旧版本原位覆盖，要求安装失败或 candidate 载荷保持不变；
6. 卸载 candidate 后重新安装 baseline，确认载荷恢复、Core Ready、用户数据未丢失；
7. 最终卸载并确认安装目录删除且没有 VisionGuard 孤儿进程。

任一步失败都会输出 FAIL 证据，不会修改已有 PASS 记录。

## 命令

```powershell
python scripts/run_windows_upgrade_acceptance.py `
  --baseline-installer D:\VisionGuard-Acceptance\Gate4\baseline\VisionGuard-gate1-<sha>.exe `
  --baseline-metadata D:\VisionGuard-Acceptance\Gate4\baseline\gate1-build-metadata.json `
  --candidate-installer D:\VisionGuard-Acceptance\Gate4\candidate\VisionGuard-gate1-<sha>.exe `
  --candidate-metadata D:\VisionGuard-Acceptance\Gate4\candidate\gate1-build-metadata.json `
  --output-dir D:\VisionGuard-Acceptance\Gate4\evidence
```

成功后，将 `upgrade-rollback-acceptance.json` 复制到 `release-evidence/`，并仅在其顶层、upgrade、
rollback 均为 PASS 时更新 `acceptance-status.json`。

## 当前状态

当前仓库只有 `1.0.0` 候选，没有版本更低且具备相同证据契约的正式 baseline，因此 Gate 4 保持
BLOCKED。需要下一套严格递增版本候选后才能执行并标记 PASS。
