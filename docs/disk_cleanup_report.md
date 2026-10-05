# 本地清理记录

## 2026-10-05：v1.0.0 发布后的清理

范围仅为项目工作区；未操作 `.git`、已安装的软件、外部验收目录、Conda 环境或用户全局缓存。

本次删除 102 个构建、下载和测试缓存目录，文件逻辑大小合计 **10,674,093,038 字节（约 9.94 GiB）**。
该数字按删除前文件大小求和，不等同于文件系统实际释放空间。

| 清理内容 | 恢复方式 |
|---|---|
| `desktop/src-tauri/target/` | 下一次 Cargo/Tauri 构建自动重建 |
| `desktop/dist/` | 在 `desktop/` 执行 `npm run build` |
| `runtime-build-core/` | 执行 Core Runtime 构建脚本 |
| `.build-tmp/`、`.ruff_cache/` | 相应工具自动重建 |
| 根目录 `pytest-cache-files-*` 和 `artifacts/pytest-*` | pytest 自动生成新的临时目录 |
| `src/`、`scripts/`、`tests/` 中的 `__pycache__/` | Python 自动重建 |
| RC、Stable 模型准备目录中的 `huggingface/`，Stable 的 `ocr-sources/`，`gate1-fresh-ocr/huggingface/` | 模型准备脚本重新下载固定 revision |

初次检查有 68 个 pytest 临时目录访问被拒绝；在沙箱外重新完整枚举后全部删除。
没有修改 ACL，也没有终止其他进程。删除前逐项检查路径位于工作区内、不包含 Git 跟踪文件或重解析点。

保留内容：

- 源码、配置、测试、锁文件和构建脚本。
- `release/v1.0.0/` 正式发布安装包、校验和、清单、SBOM 和证据。
- RC 发布材料、`release-evidence/`、实验与验收报告、模型来源记录和训练 checkpoint。
- `runtime-dist-core/`、当前 Core Models、唯一 VLM 模型副本和基础检测权重。
- `desktop/node_modules/`，方便后续开发。
- 未公开的面试准备笔记和老奶奶使用说明。

文档清理：删除无引用且已经过时的 `RELEASE_NOTES_v1.0.0-rc.1.md` 草稿。
正式版本的发布说明保存在 Release 资产中；历史架构决策见 [release_history.md](release_history.md)。
此记录替代冗长的旧目录清单，旧记录可以从 Git 历史恢复。

## 历史清理

2026-09-27 曾清理约 59.00 GiB，包括旧 VLM Runtime、重复模型、分卷和构建产物。
当时的详细清单保存在 Git 历史中。当前目录管理原则见 [disk_management.md](disk_management.md)。
