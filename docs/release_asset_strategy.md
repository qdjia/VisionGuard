# Release Asset Strategy

审计日期：2026-09-25。

## 平台限制不是同一件事

| 通道 | 当前官方限制 | VisionGuard 决策 |
|---|---|---|
| 普通 Git 仓库文件 | 命令行单文件上限 100 MiB | 不提交 Runtime、模型或安装器 |
| Git LFS | GitHub Free / Pro 单文件 2 GB；不同计划额度不同 | 不作为最终用户发行基础设施 |
| GitHub Release asset | 每文件必须小于 2 GiB；每个 Release 最多 1000 个 asset；总 Release 大小和带宽无固定上限 | Core installer 和 1 GiB Advanced AI parts 可使用 |

官方依据：

- [GitHub 普通仓库大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Git LFS 单文件限制](https://docs.github.com/en/enterprise-cloud@latest/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
- [GitHub Releases 资产限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

## 决策

第一版 RC 采用 GitHub Release 分卷资产，默认每卷 1024 MiB：

- `VisionGuard-Setup-1.0.0-rc.1.exe`
- `advanced-ai-manifest.json`
- VLM Runtime `.partNN`
- VLM Models `.partNN`
- `SHA256SUMS.txt`
- `release-manifest.json`
- CycloneDX SBOM
- Release Notes

1 GiB 明显低于 2 GiB 边界，也为托管层额外元数据和以后体积波动保留空间。用户不手工合并分卷；Desktop 读取 manifest 并跨分卷流式解压。

如果 GitHub 资产维护成本过高，VLM Models 可迁移到 Hugging Face Hub，Runtime 仍保留在 GitHub Release。迁移前必须保证模型包的 Apache-2.0 文本、模型卡、来源 revision 和哈希完整。个人网盘和临时分享站不作为正式基础设施。

本阶段不实现网络下载器。未来下载器必须同时支持 resume、retry、SHA-256 和原子安装。
