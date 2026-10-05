# Release Operations

本文集中维护候选包验收、硬件记录、签名、模型许可和资产策略。当前是否允许发布由
[`release_gate.md`](release_gate.md) 决定。

## 默认发行资产

默认使用 Tauri NSIS + Slim CPU Core + Advanced AI Online Bootstrap：

- 安装器携带 Core Runtime、Core Models、bootstrap manifest、lock 和项目 wheel；
- 不携带 Qwen 权重、外部 wheel、PyTorch CUDA Runtime 或旧 `.partNN` 分卷；
- Advanced AI 只能从 manifest 固定的 Python、PyTorch 和 Hugging Face 官方来源获取；
- 安装失败不得替换已激活组件，也不得影响 Fast Review。

旧 VLM Runtime/Models 分卷仅用于显式 fallback 和历史复现。生成的 Release、Runtime、
模型分卷与 staging 在上传或验证结束后应删除，需要时由脚本重新生成。

## Split Windows 验收

当前验收拆分为 Clean Core、Fresh-user GUI 和 Advanced AI GPU 三个 Gate。具体环境、命令与
证据边界见 [`windows_acceptance.md`](windows_acceptance.md)。以下流程由三个 Gate 分别覆盖，
不再要求一台机器同时证明所有性质。

Gate 1 使用 GitHub Actions 临时自构建 candidate：Build Job 从当前 commit 重建 Core Models、
Core Runtime 和 Tauri/NSIS installer，Smoke Job 在另一个 `windows-latest` runner 下载同一次运行的
artifact 后验收。该 artifact 不是 Final Candidate 或 GitHub Release，不得跨 commit 复用。

候选包必须在没有源码仓库、开发工具、已有模型缓存或旧组件残留的独立 Windows 环境执行：

1. 核对安装器、manifest 和资产 SHA-256。
2. 安装、首次启动，确认 Slim Core readiness 与 Fast Review。
3. 确认运行流量仅访问 loopback；安装/更新阶段的官方源网络访问需与 manifest 一致。
4. 安装 Advanced AI，验证空间预检、断点续传、取消、失败恢复和原子激活。
5. 执行 Deep Review，确认使用本地 VLM sidecar，图片未发送至云端推理 API。
6. 验证更新、回滚、卸载、重装、窗口关闭和无 orphan process。
7. 回放可再分发的历史真实图片集，保存版本、硬件、哈希、日志摘要和验收人。

## RC Checklist

- [x] GitHub-hosted Windows Clean Core 验收 PASS
- [x] 当前机器新普通用户 Fresh-user GUI 验收 PASS
- [x] RTX 4060 独立受管环境 Advanced AI GPU 验收 PASS
- [x] `overall_clean_environment` 聚合结果 PASS
- [x] 完整 fresh-cache Advanced AI 下载与恢复流程通过
- [x] Core readiness、Fast Review、Deep Review 和 fail-safe 通过
- [x] 动态端口、session token、关闭与无 orphan process 通过
- [x] 更新、回滚、卸载与重装通过
- [x] 历史真实图片回归达到 `PASS_WITH_LIMITATION`；独立干净机复验未完成，`v1.0.0` 由项目所有者显式接受风险
- [x] Detector AGPL 来源、Corresponding Source、commit/tag 映射完整
- [x] SBOM、LICENSE、NOTICE 和第三方声明由构建器写入候选包
- [x] 最终 RC 候选包未包含禁止的模型、wheel、CUDA/NVIDIA DLL 或旧分卷
- [x] `python scripts/validate_release.py <candidate> --rc` 无绕过通过

最终 RC 必须使用 `python scripts/build_release.py --version 1.0.0-rc.1 --final-rc`。
该模式要求 Git tracked tree 干净，禁止复用旧二进制或旧输出，强制重建 Core Models，且只允许
online-bootstrap 分发。构建结束会自动运行严格 RC validator；失败时不得创建 Tag 或 Release。

Stable 候选必须使用 `python scripts/build_release.py --version 1.0.0 --stable`。该模式复用相同的
干净源码、全量重建、online-bootstrap 和禁止跳过校验约束，但生成 `release_channel=stable`，
在 Release Notes 中强制披露已豁免风险，并自动执行 `validate_release.py --stable`。本地通过不会
自动创建 Tag、GitHub Release 或公开发布。

## 硬件验证边界

当前仅在 Windows、NVIDIA GeForce RTX 4060 Laptop 8 GiB、Driver 580.97 上验证过
Qwen3-VL-2B 本地推理与 CUDA 12.8 环境。这是 `Validated On`，不是最低硬件要求。
最低 GPU、VRAM、RAM 和 CPU 要求必须经过多设备重复测试后才能声明。

## 签名策略

当前没有 Authenticode 证书。未签名安装包可能触发 SmartScreen，必须在 Release Notes 和下载页
显著披露，并要求用户核对 SHA-256。自签名只可用于流程测试，不能描述为正式签名。
项目所有者已对且仅对 `v1.0.0` 接受未签名发行风险；后续版本必须重新签名或重新作出明确决定。

## Stable 风险豁免

`release-evidence/stable-release-risk-waiver.json` 是 `v1.0.0` 的机器可读决定记录。它同时满足以下原则：

- 只接受独立干净机历史回归未完成与 Authenticode 未签名两项已知风险。
- 原始要求状态必须保持 `NOT_COMPLETED`，不得改写为 `PASS`。
- 必须记录项目所有者、日期、版本范围、理由和剩余风险。
- 必须披露干净机复验未完成、安装包未签名、SmartScreen 风险和 SHA-256 校验方式。
- 不适用于未来版本；缺失或被篡改时 Stable validator 失败关闭。

## 模型与依赖许可

| 组件 | 当前依据 | 决策 |
|---|---|---|
| Qwen3-VL-2B-Instruct | Apache-2.0 元数据、固定 revision 与文件哈希 | 允许按记录来源获取 |
| PaddleOCR 模型 | Apache-2.0 来源和模型文件清单 | 允许按证据链分发 |
| Ultralytics YOLO 衍生 Detector | AGPL-3.0 或适用 Enterprise 条款 | AGPL 路径下有条件允许 |
| PyTorch/CUDA 依赖 | 官方 PyTorch 索引在线安装 | 默认 Release 不直接再分发其二进制 |

项目根许可证不会自动重新许可第三方模型或依赖。详细 Detector 证据见
[`detector_provenance.md`](detector_provenance.md)，最终发行声明见
[`release_licenses.md`](release_licenses.md)。

## 发布操作规则

- 普通本地校验只证明内部一致性，不代表可公开发布。
- RC validator 未通过时，不创建 Tag、Pre-release 或 Stable Release。
- 最终构建必须重新生成 SBOM、manifest、SHA-256 和来源 commit。
- 上传后本地生成资产可删除；仓库长期只保留源码、配置、lock、模板和小型证据。
