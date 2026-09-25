# VisionGuard AGPL-3.0-only 迁移记录

状态：2026-09-26 已完成源码与发行元数据对齐；最终 RC 尚未重建。

## 为什么迁移

VisionGuard 选择开放源码发行，并希望在包含 Ultralytics 派生 Detector 的发行方案中保持统一、可审计的开源边界。项目自有代码从 MIT 改为 GNU Affero General Public License v3.0 only，SPDX 标识为 `AGPL-3.0-only`。

## 迁移前状态与所有权审计

- 根 `LICENSE` 曾为 MIT，版权行为 `Copyright (c) 2026 qdjia`。
- `git shortlog -sne --all` 与完整 author 历史只发现 `qdjia <qidongja@gmail.com>`。
- 未发现 merge commit、外部贡献者或已纳入仓库的 vendored 第三方源码。
- 因此，仓库证据未显示需要额外贡献者同意的重许可阻断项。该结论是工程审计，不是法律意见。

迁移保留了原版权信息于根 `NOTICE`。迁移前已合法取得的代码副本仍受当时适用许可约束；本记录不追溯改写历史发布事实。

## 新发行模型

- VisionGuard 自有代码：`AGPL-3.0-only`。
- 第三方依赖、模型、Runtime 和资产：继续使用各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
- 安装、模型/组件获取与更新：允许联网。
- 审核推理：本地执行，不依赖云端推理 API，也不提供向云端审核服务上传图片的实现。
- Fully Offline / Real Offline：不是 v1.0 产品承诺，也不再是 RC 阻断门。

## 源码可用性与发布义务

发行候选必须携带项目许可证与 Notice、生成带项目许可证的 SBOM、记录对应源码 commit 和预期 tag，并保留构建脚本、模型来源、修改记录与第三方声明。通过网络向用户提供修改后的适用程序时，同样需要评估并履行 AGPL 的 Corresponding Source 要求。

AGPL 是自由/开源许可证，并不等于“禁止商业使用”。任何发行者仍须遵守其复制、修改、分发和网络交互相关义务。

## Detector 影响

当前 Ultralytics Detector 从 `NOT_ALLOWED`（旧 MIT RC 路径）改为 `ALLOWED_WITH_CONDITIONS`（AGPL 开源路径）。只有 `release-evidence/detector-provenance.json` 所列条件全部随最终候选实现后，Detector gate 才可通过。此变化不解决独立的 NVIDIA 原生二进制许可阻断。

## 历史文档范围

Phase 16–19、旧 RC blocker/acceptance 报告描述的是当时的 MIT 与离线目标，作为历史快照保留。当前政策以本文件、`README.md`、`docs/release_gate.md` 和机器可读 release evidence 为准；冲突内容均视为已被本次迁移取代。

参考：GNU AGPL v3 正文 <https://www.gnu.org/licenses/agpl-3.0.html>；SPDX `AGPL-3.0-only` <https://spdx.org/licenses/AGPL-3.0-only.html>。
