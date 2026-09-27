# Split Windows Acceptance

VisionGuard 不再用一台“全新、带 GPU、同时完成 GUI 与在线安装”的机器承担所有证明。
Windows 验收拆成三个边界明确的 Gate；只有三者全部 PASS，才能把
`overall_clean_environment` 标为 PASS。

## Gate 1：Clean Core Acceptance

环境：GitHub-hosted `windows-latest` runner。它证明候选安装器中的 CPU Core 不依赖开发机，
不证明 GPU、真实用户 GUI 或完整操作系统硬件兼容性。

Workflow：`.github/workflows/windows-release-smoke.yml`

手动触发不需要输入参数。进入 GitHub **Actions → Windows Release Smoke → Run workflow** 后，
`build-candidate` 会从当前 commit 的 tracked source、锁文件和固定官方模型来源构建临时 Core-only
NSIS candidate，自动计算 SHA-256，并上传 `visionguard-gate1-candidate`。随后独立的
`clean-core-smoke` Windows runner 下载该 artifact，并用 build metadata 重新校验 commit、run ID、
文件名和 SHA-256。

Workflow 会静默安装到隔离目录、定位安装包内 Desktop/Core Runtime/Core Models、
扫描禁止的 CUDA/NVIDIA 二进制、执行 `/health/live`、`/health/ready`、`/v1/meta` 和 Fast Review，
最后静默卸载并检查 orphan process。Candidate artifact 保留 5 天，仅用于同一次 CI 验收；evidence
artifact 不重复包含 installer，也不会创建 GitHub Release、Tag 或公开下载。

PR 触发只运行验收合同测试，不执行重型 installer build，也不能产生 Gate 1 PASS。Gate 1 PASS
只证明 evidence 中 `git_sha` 对应的 commit；installer、runtime 或 Core Models 变化后必须重新运行。

## Gate 2：Fresh-user GUI Acceptance

环境：当前 Windows 的新普通本地用户。它证明安装器和 GUI 不依赖开发账户的 PATH、AppData、
Conda、Node、Rust、源码路径或模型缓存；它不等价于全新 Windows。

执行方式和记录表见 [`fresh_user_gui_acceptance.md`](fresh_user_gui_acceptance.md)。Codex 不自动
创建、删除或修改 Windows 用户。Gate 2 不要求下载完整 Advanced AI，只确认入口正确显示为
Not Installed 并可开始安装。

## Gate 3：Advanced AI GPU Acceptance

环境：当前 RTX 4060 Laptop 8 GiB 开发机，但使用全新的 VisionGuard-managed data root 和该 root
下独立的 pip/Hugging Face/staging cache。它证明官方源 bootstrap、CUDA、本地 VLM 进程和
Core→RemoteVLMProvider 集成；它不等价于独立 clean machine。

统一入口：

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python scripts/run_advanced_ai_gpu_acceptance.py `
  --data-dir D:\VisionGuard-Acceptance\advanced-ai-fresh
```

目录必须不存在或为空。网络中断后的同目录重试使用 `--resume`；runner 默认在一次调用中最多
尝试两次。当前 `models/vlm-models-v1` fallback 不会被删除或用作 bootstrap 下载源。

Runner 记录真实下载/安装测量，启动 managed Python VLM，完成三次请求和单次模型初始化验证，
再启动 packaged Core 验证路由、VLM 崩溃 fail-safe 和不重启 Core 的 VLM 恢复。推理阶段设置
Hugging Face/Transformers offline 标志，不调用云端推理 Provider。

## Evidence model

| Gate | Evidence | Allowed status |
|---|---|---|
| Clean Core | `release-evidence/windows-core-acceptance.json` | PASS / BLOCKED / FAIL |
| Fresh-user GUI | `release-evidence/fresh-user-gui.json` | PASS / BLOCKED / FAIL |
| Advanced AI GPU | `release-evidence/advanced-ai-gpu-acceptance.json` | PASS / BLOCKED_NETWORK / BLOCKED / FAIL |
| Aggregate | `release-evidence/windows-acceptance-summary.json` | PASS / BLOCKED / FAIL |

下载 `visionguard-gate1-evidence` artifact 后，将 Gate 1 JSON 放入 `release-evidence/`，完成 Gate 2/3
记录后运行：

```powershell
python scripts/run_windows_acceptance.py
```

聚合器不联网访问 GitHub API，也不会把 missing、BLOCKED 或 BLOCKED_NETWORK 转成 PASS。

## Claim boundary

- Gate 1 PASS：可声明 packaged Core 在 GitHub-hosted 临时 Windows runner 自包含运行。
- Gate 2 PASS：可声明 GUI 在当前机器的新普通用户配置下不依赖开发账户。
- Gate 3 PASS：可声明 Advanced AI 在已记录 RTX 4060 配置上从空受管环境安装并本地推理。
- 三者 PASS：可声明 split clean-environment acceptance PASS。
- 任何组合都不能自动扩展为“完全离线”“所有 GPU 兼容”或“独立全新 GPU Windows”。
