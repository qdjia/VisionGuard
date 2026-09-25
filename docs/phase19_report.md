# Phase 19 — VisionGuard v1.0 Release Gate Report

日期：2026-09-25  
结论：**本地候选构建通过；RC Gate 未通过，不建议 Tag 或公开发布。**

## 1. Release Gate Summary

本阶段完成了 Advanced AI 真实分卷、Desktop 原子安装核心、Core-bundled NSIS、本地 release manifest、SHA-256、CycloneDX SBOM、发行策略和许可证审计。`validate_release.py` 的 local gate 通过；`--rc` 按设计失败，因为 clean-machine、历史回归、公开分发许可和最终 native redistribution gate 未完成。

## 2. Advanced AI Package Format

- 格式：两个独立 ZIP 逻辑流（VLM Runtime / VLM Models），各自切成有序 `.partNN`。
- 清单：`advanced-ai-manifest.json` schema v1。
- 每卷字段：index、file、size_bytes、sha256。
- 组件字段：version、archive size、unpacked size、combined archive SHA-256。
- 默认 chunk：1024 MiB，低于 GitHub Release 单 asset 2 GiB 限制。
- 安装器不会生成完整 reconstructed ZIP；自定义 multipart `Read + Seek` 直接交给 ZipArchive。

## 3. Measured Sizes

| Item | Bytes | Approx. |
|---|---:|---:|
| Core Runtime installed | 748,419,793 | 0.697 GiB |
| Core Models installed | 156,803,606 | 0.146 GiB |
| Core-only installed | 905,223,399 | 0.843 GiB |
| Core NSIS installer | 531,009,419 | 506.4 MiB |
| VLM Runtime archive | 4,528,446,114 | 4.217 GiB |
| VLM Models archive | 4,266,645,085 | 3.974 GiB |
| Advanced AI parts total | 8,795,091,199 | 8.191 GiB |
| Additional free space required | 9,673,283,926 | 9.009 GiB |
| Peak including retained source parts | 18,468,375,125 | 17.200 GiB |

Runtime parts：5（4 × 1 GiB + 233,478,818 bytes）。Models parts：4（3 × 1 GiB + 1,045,419,613 bytes）。

## 4. Installation Lifecycle

1. 用户选择 manifest。
2. 校验平台、架构、版本、路径、分卷顺序、重复、缺卷、大小。
3. 计算实际所需空间并检查目标卷可用空间。
4. 流式读取每卷，同时校验 part SHA-256 和 combined archive SHA-256。
5. 流式解压至 `.staging-<id>`，报告真实 I/O 字节进度。
6. 校验 Runtime manifest / executable 和 Model manifest / VLM files。
7. 把版本目录移入正式 component root。
8. 原子写入 `components.json`，旧 pointer 保存为 `components.previous.json`。

取消使用原子标记，在块边界 fail closed；staging 被清理，active pointer 不改变。更新失败会恢复被替换的同版本目录。版本不同的旧组件保留，可通过 previous registry 回滚。

相同版本组件会复用：例如 Runtime v2 + Models v1 更新只解压和替换 Runtime，不重新安装已激活的 Models v1。当前 package builder 仍生成 Runtime + Models 完整包；真正的单组件 delta package 留待后续版本。

卸载前 Desktop 先停止 VLM，再删除 active VLM Runtime / Models 与 registry；Core 不受影响。Desktop reinstall / upgrade 的 Advanced AI 数据位于 app local data，设计上不随安装目录替换。

## 5. Local RC Build

输出：`release/v1.0.0-rc.1/`（Git ignored）。

- `VisionGuard-Setup-1.0.0-rc.1.exe`
- `advanced-ai-manifest.json`
- 9 个 Advanced AI parts
- `SHA256SUMS.txt`
- `release-manifest.json`
- `RELEASE_NOTES.md`
- `sbom/desktop.cdx.json`
- `sbom/core-runtime.cdx.json`
- `sbom/vlm-runtime.cdx.json`

NSIS 首次构建失败的根因是 Tauri 缓存中的 WebView2 offline installer 长度与上游当前响应不一致。Verbose 重试重新下载正确文件后成功，最终 NSIS 使用 LZMA，输入约 1.134 GB，输出 531,009,419 bytes。

Local validation：**PASS**。  
RC validation：**FAIL (expected, fail closed)**。

## 6. Runtime / GUI Verification

- Python：170 passed。
- Frontend：46 passed；lint、TypeScript、production build 通过。
- Rust：21 passed（10 unit + 11 integration）；fmt、check 通过。
- Packaged Core smoke：live / ready / meta / Fast Review 成功；VLM unavailable 时 capability 正确；进程正常停止。
- Advanced AI real parts：生成后逐卷 SHA-256 校验通过。
- Desktop shortcut / Start Menu / Single instance / real window close：配置存在，但本阶段没有在 clean machine 人工确认。
- Installer install / reinstall / Desktop upgrade / full uninstall：尚未在 clean machine 执行。
- Offline clean-machine flow：尚未执行。

## 7. Distribution and Licensing

GitHub 官方文档确认：普通仓库单文件 100 MiB；Git LFS 与 Release asset 是不同通道；Release asset 单文件必须小于 2 GiB，单 Release 最多 1000 assets，总大小和带宽无固定上限。策略选择 GitHub Release + 1 GiB parts；不使用个人网盘。自动网络下载留给 v1.1。

SBOM：CycloneDX 1.6；Desktop 815 components、Core Runtime 443、VLM Runtime 225。Python 组件优先来自冻结 Runtime 的 `.dist-info/METADATA` 精确版本（无冻结产物时才回退到 release requirements profile），native 文件来自实际打包目录，不使用 dev `pip freeze`。

许可证结论：

- Qwen3-VL-2B-Instruct：官方模型卡标记 Apache-2.0；条件通过，需随包附证据。
- Paddle：官方代码为 Apache-2.0；条件通过，最终 OCR 模型 notice 仍需核对。
- Detector / Ultralytics derivative：**BLOCKED**。
- PyTorch 主体：条件通过；最终第三方 notices 必须随包。
- CUDA / cuDNN native redistribution：**BLOCKED**，需逐项对照 NVIDIA EULA Attachment A。
- Code signing：当前 unsigned；RC 可显著披露，Stable 建议受信任 Authenticode。

## 8. Historical Regression and Legacy Verdict

Phase 6 / 8 / 9 / 11 自动化测试仍通过全量 Python suite，但尚未把所有历史 fixtures / hard cases 以新 Core + VLM 打包架构完整重放并保存独立证据。

Legacy Full Runtime verdict：**Reference Only，尚不能升级为 Safe To Retire**。本阶段没有删除 Legacy source。

## 9. Current Blockers

1. Clean Windows / Sandbox 全流程验收未执行。
2. Installer shortcut、Start Menu、single instance、reopen、reinstall、upgrade、full uninstall 未在干净机人工确认。
3. Advanced AI 真实大包尚未通过 Desktop GUI 完整安装 / 取消 / 升级 / 回滚 / 卸载验收。
4. Detector 权重公开再分发路径未解决。
5. VLM Runtime native CUDA / PyTorch 文件未完成逐项再分发复核。
6. Historical hard-case regression 缺少独立新架构记录。
7. Authenticode 未配置；Stable signing gate 未满足。

## 10. Versioning Recommendation

| Decision | Recommendation |
|---|---|
| Commit | Yes，自动化和 local build 已达到可提交状态 |
| RC Tag | **No** |
| Recommended RC tag | N/A（Gate 通过后再使用 `v1.0.0-rc.1`） |
| Stable Tag | **No** |
| Recommended Stable tag | N/A |
| GitHub Pre-release | **No** |
| GitHub Stable Release | **No** |

Next Release Gate：在干净 Windows 完成安装/GUI/离线/升级/卸载验收，解决 detector 与 native redistribution blocker，执行历史 hard-case regression，然后重新构建最终资产并要求 `python scripts/validate_release.py --rc` 通过。

## 11. Required 48-point Handoff

| # | 汇报项 | 结果 |
|---:|---|---|
| 1 | Release Gate Summary | Local PASS；RC BLOCKED |
| 2 | Advanced AI Package Format | Runtime / Models 两个 ZIP 逻辑流，按 `.partNN` 分卷，manifest schema v1 |
| 3 | Runtime Part Sizes | 5 卷：4 × 1 GiB + 233,478,818 bytes |
| 4 | Model Part Sizes | 4 卷：3 × 1 GiB + 1,045,419,613 bytes |
| 5 | Total Advanced AI Size | 8,795,091,199 bytes（8.191 GiB） |
| 6 | Peak Install Disk Requirement | 含保留源分卷约 17.200 GiB；额外安装空间约 9.009 GiB |
| 7 | Advanced AI Install Flow | manifest 校验 → 磁盘预检 → 流式校验/解压 → staging 校验 → 原子激活 |
| 8 | Install Cancellation | 块边界取消，清理 staging，不改变 active pointer；GUI 人工验收待完成 |
| 9 | Atomic Activation | `components.json` 原子替换，previous registry 留存 |
| 10 | Upgrade | Runtime / Models 独立版本；相同版本组件复用；真实大包人工验收待完成 |
| 11 | Rollback | previous registry swap 已实现；真实大包人工验收待完成 |
| 12 | Uninstall | 停止 VLM 后删除 Advanced AI，保留 Core；人工验收待完成 |
| 13 | Reinstall | 设计与接口已覆盖；干净机验收待完成 |
| 14 | Core Installer Size | 531,009,419 bytes（506.4 MiB） |
| 15 | Core Installed Size | 905,223,399 bytes（0.843 GiB） |
| 16 | Clean-machine Environment | 当前机器无 Windows Sandbox；未执行，BLOCKED |
| 17 | Installer Test | NSIS 构建成功；干净机安装测试待执行 |
| 18 | Desktop Shortcut | 配置存在；干净机确认待执行 |
| 19 | Start Menu | 配置存在；干净机确认待执行 |
| 20 | Single Instance | 配置/既有测试存在；真实安装确认待执行 |
| 21 | Core Ready | Packaged Core `/live`、`/ready`、`/meta` smoke PASS |
| 22 | Fast Review | Packaged Core smoke PASS |
| 23 | Advanced AI Import | 流式安装实现；真实大包 GUI 端到端待执行 |
| 24 | Deep Review | Phase 18 packaged VLM smoke 有证据；本阶段干净机待执行 |
| 25 | Routing-triggered VLM | 既有自动化覆盖；本阶段干净机待执行 |
| 26 | Offline Acceptance | 架构支持；干净机全流程待执行 |
| 27 | Window Close | 进程停止逻辑存在；真实窗口验收待执行 |
| 28 | Orphan Process | 自动化/既有 smoke 未发现；干净机任务管理器复核待执行 |
| 29 | Desktop Reinstall | 待干净机执行 |
| 30 | Desktop Upgrade | 待干净机执行 |
| 31 | Full Uninstall | 待干净机执行 |
| 32 | Asset Hosting Strategy | GitHub Release + 1 GiB parts；不使用个人网盘；自动下载留待 v1.1 |
| 33 | GitHub Asset Limit Findings | Repo 100 MiB；Release 单 asset < 2 GiB、最多 1000 个 |
| 34 | SBOM | CycloneDX 1.6：Desktop 815、Core 443、VLM 225 components |
| 35 | Third-party License Result | PARTIAL；notices 已整理，最终逐项法律复核未完成 |
| 36 | Detector Weight License Result | BLOCKED；需 AGPL 合规、商业许可或替换权重 |
| 37 | Qwen License Result | Apache-2.0，条件通过，发行包仍需附证据 |
| 38 | Paddle License Result | Apache-2.0，条件通过，OCR 模型 notice 仍需核对 |
| 39 | CUDA/PyTorch Redistribution Result | PyTorch 条件通过；CUDA/cuDNN native inventory BLOCKED |
| 40 | Code Signing Status | UNSIGNED；RC 必须披露，Stable 建议可信 Authenticode |
| 41 | Historical Regression | Python 170 PASS；独立新架构 hard-case 记录仍 PENDING |
| 42 | Legacy Runtime Verdict | Reference Only；不是 Safe To Retire；未删除源码 |
| 43 | Release Manifest | schema v3 已生成；local validator PASS |
| 44 | SHA256 | installer、manifest、全部 9 个 parts 均写入 `SHA256SUMS.txt` 并校验 |
| 45 | RC Validation Result | FAIL EXPECTED / fail closed |
| 46 | Current Blockers | clean machine、Advanced AI GUI 生命周期、许可证/native、历史回归、签名 |
| 47 | Recommended Commit Message | 见任务交付回复；允许提交，不代表允许 Tag/Release |
| 48 | Versioning Recommendation | Desktop 1.0.0；候选目录 `1.0.0-rc.1`；当前不创建任何 Tag |
