# Release Asset Strategy

审计日期：2026-09-25。

## 平台限制不是同一件事

| 通道 | 当前官方限制 | VisionGuard 决策 |
|---|---|---|
| 普通 Git 仓库文件 | 命令行单文件上限 100 MiB | 不提交 Runtime、模型或安装器 |
| Git LFS | GitHub Free / Pro 单文件 2 GB；不同计划额度不同 | 不作为最终用户发行基础设施 |
| GitHub Release asset | 每文件必须小于 2 GiB；每个 Release 最多 1000 个 asset；总 Release 大小和带宽无固定上限 | 只发布小型 Core installer 与实际发行元数据 |

官方依据：

- [GitHub 普通仓库大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Git LFS 单文件限制](https://docs.github.com/en/enterprise-cloud@latest/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
- [GitHub Releases 资产限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

## 决策

默认 RC 采用 online-bootstrap：

- `VisionGuard-Setup-1.0.0-rc.1.exe`
- 内嵌 `advanced-ai-bootstrap-manifest.json` 与约 0.2 MiB 的 VisionGuard VLM wheel
- `SHA256SUMS.txt`
- `release-manifest.json`
- CycloneDX SBOM
- Release Notes
- Third-Party Notices、release license report 与 detector provenance

旧的 VLM Runtime/Model `.partNN` 分卷只在显式 `--advanced-ai-mode bundled` 时生成，状态为 legacy/fallback/reference。默认 Release 不携带 PyTorch wheel、CUDA/NVIDIA DLL 或 Qwen 权重；用户确认安装后才从固定官方源获取。

因此 GitHub 单资产 2 GiB 上限不再决定默认 Advanced AI 发行结构。构建器和 validator 会拒绝在线模式 staging 中出现 CUDA/NVIDIA DLL、外部 wheel 或模型权重。

模型固定从 Hugging Face 上的 Qwen 官方仓库及 immutable revision 获取；PyTorch 固定从官方 CUDA 12.8 index 获取。个人网盘、自建镜像和临时分享站不作为正式基础设施。

网络失败不会修改 active registry；重试复用已通过哈希的 Python/PyPA 下载缓存。模型下载器使用 Hugging Face 官方客户端的续传能力，完成必需文件、revision、大小和已知 SHA-256 校验后才原子激活。
