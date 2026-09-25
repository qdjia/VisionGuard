# Clean-machine Acceptance Record

状态：**NOT EXECUTED — RC BLOCKER**  
候选版本：`1.0.0-rc.1`（尚未创建 Tag）

该记录必须在没有 Python、Node、Rust、源码仓库、Conda、开发虚拟环境和模型缓存的 Windows Sandbox 或干净 VM 中填写。开发机结果不能代替此记录。

## 环境

| 字段 | 记录 |
|---|---|
| Windows 版本 / Build | 待填写 |
| CPU / RAM | 待填写 |
| GPU / VRAM | 待填写 |
| Driver | 待填写 |
| Installer 文件名 / SHA-256 | 待填写 |
| 测试日期 / 执行人 | 待填写 |

## 验收步骤

- [ ] 断网安装 Core installer
- [ ] Start Menu 与桌面快捷方式存在，图标和 target 正确
- [ ] 双击启动，Core Ready，Fast Review 成功
- [ ] 连续双击只保留一个 Desktop / Core / VLM 实例
- [ ] 本地导入 Advanced AI manifest，显示真实字节进度
- [ ] 缺卷、篡改卷、版本不兼容均 fail closed
- [ ] 取消安装不影响旧 active component
- [ ] Advanced AI Ready，Deep Review 与 Routing-triggered VLM 成功
- [ ] 关闭窗口后 Core、VLM、端口和 GPU process 均退出
- [ ] 重开后 components 保留
- [ ] VLM Runtime / Models 独立升级、active switch 与 rollback 成功
- [ ] 移除 Advanced AI 后 Core 仍可工作
- [ ] Desktop reinstall / upgrade 保留 Advanced AI
- [ ] Full uninstall 选项删除全部用户数据（若实现）
- [ ] 卸载 VisionGuard 后无 orphan process

截图、进程列表、端口检查、日志摘要与失败项：待填写。不能只写 “passed”。

## 逐项证据记录模板

每一行必须填写 Actual、Result 和 Evidence；`PASS` 不能只依据开发机自动化结果。

| # | Step | Expected | Actual | Result | Evidence |
|---:|---|---|---|---|---|
| 1 | 校验全部候选文件 SHA-256 | 与 `SHA256SUMS.txt` 全部一致 | 待填写 | BLOCKED | 待填写 |
| 2 | Core NSIS install | 无开发工具依赖，安装成功 | 待填写 | BLOCKED | 待填写 |
| 3 | Desktop shortcut | 存在，图标与 target 正确 | 待填写 | BLOCKED | 待填写 |
| 4 | Start Menu | 入口存在且可启动 | 待填写 | BLOCKED | 待填写 |
| 5 | First launch / Core Ready | Core 启动并 Ready | 待填写 | BLOCKED | 待填写 |
| 6 | Single instance | 连续启动只存在一组实例 | 待填写 | BLOCKED | 待填写 |
| 7 | Fast Review | 真实 GUI 完成并返回结构化结果 | 待填写 | BLOCKED | 待填写 |
| 8 | No-VLM fail-safe | VLM-required 样本不产生 unsafe low；保持 manual review | 待填写 | BLOCKED | 待填写 |
| 9 | Advanced AI parts discovery | 找到真实完整 9 分卷 | 待填写 | BLOCKED | 待填写 |
| 10 | Hash / disk preflight | 哈希和空间检查完成；损坏/缺卷 fail closed | 待填写 | BLOCKED | 待填写 |
| 11 | Atomic activation | 安装成功才切换 active；取消不破坏旧组件 | 待填写 | BLOCKED | 待填写 |
| 12 | Advanced AI Ready | Runtime 与 models 被识别 | 待填写 | BLOCKED | 待填写 |
| 13 | Deep Review | Qwen lazy load、结构化输出、fusion 成功 | 待填写 | BLOCKED | 待填写 |
| 14 | Routing-triggered VLM | Cascaded 样本自动调用 VLM | 待填写 | BLOCKED | 待填写 |
| 15 | Disable network adapter | 系统确认无外网；不是只设 offline env | 待填写 | BLOCKED | 待填写 |
| 16 | True-offline replay | Launch、Core、Fast、Deep、routing VLM 全部成功 | 待填写 | BLOCKED | 待填写 |
| 17 | GUI lifecycle | Select、Drag & Drop、overlays、details、theme、restart/stop 成功 | 待填写 | BLOCKED | 待填写 |
| 18 | Window X / no orphan | Desktop、Core、VLM、端口、GPU process 全部退出 | 待填写 | BLOCKED | 待填写 |
| 19 | Reopen | 自动识别 Core/Advanced AI，无需重装模型 | 待填写 | BLOCKED | 待填写 |
| 20 | Upgrade / rollback | Desktop/runtime/model upgrade；失败激活保留旧 active | 待填写 | BLOCKED | 待填写 |
| 21 | Advanced AI uninstall | 移除后 Core/Fast Review 仍工作 | 待填写 | BLOCKED | 待填写 |
| 22 | Desktop uninstall / reinstall | 无 orphan；重装成功；数据选项行为符合说明 | 待填写 | BLOCKED | 待填写 |

建议 Evidence 使用脱敏截图编号、命令输出文件名和日志时间戳。关闭窗口后记录：

```powershell
Get-Process | Where-Object ProcessName -Match 'visionguard|core|vlm'
Get-NetTCPConnection -State Listen | Sort-Object LocalPort
nvidia-smi
```

## 2026-09-25 environment availability check

开发机未发现 Windows Sandbox、Hyper-V PowerShell module、VMware `vmrun` 或 VirtualBox `VBoxManage`。开发机已有 Python/Conda、Node、Rust、源码和模型缓存，因此不符合 clean-machine 定义。本记录不能在当前环境签署 PASS。

## User Action Required

Action: 提供独立 Windows Sandbox、全新 VM 或物理测试机并执行完整验收。

Why: 当前开发机含完整开发栈、缓存和已部署模型，不能证明安装包自包含、真实离线或无 orphan。

Exact Steps:

1. 准备未安装 Python、Conda、Node、Rust、Git 或 VisionGuard 的 Windows。
2. 在开发机四个外部 blocker 关闭并重建后，复制最终候选的全部文件，不要只复制安装器。
3. 逐项核对 `SHA256SUMS.txt`，记录环境和候选哈希。
4. 按上方 22 行执行安装、GUI、真断网、生命周期、升级、回滚、卸载和重装测试。
5. 保存不含用户名、私人路径或私人图片的截图、进程、端口和日志摘要。
6. 把填写后的记录与脱敏证据交回；不要手工把 manifest Gate 改为 PASS。

Evidence Needed: 已填写表格、Windows/硬件/网络状态、截图编号、进程与端口输出、日志摘要、最终候选 SHA-256。

Blocks RC: **Yes**。
