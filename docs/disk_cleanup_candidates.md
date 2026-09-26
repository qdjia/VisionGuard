# 磁盘清理候选

本阶段不自动进行大规模删除。确认新 online-bootstrap 回归通过后再按以下分类处理。

| 路径/内容 | 分类 | 原因 |
|---|---|---|
| `runtime-dist-vlm/` | REBUILDABLE | 旧 PyInstaller VLM Runtime 产物，可由保留的构建脚本重建 |
| `release/`、`release-staging/` | REBUILDABLE | 本地候选与 staging，不是源码 |
| 旧 Advanced AI `.partNN` 与 ZIP | SAFE_DELETE | 默认发行不再使用，确认没有人工验收依赖后可删 |
| 失败的 `advanced-ai/staging/install-*` | SAFE_DELETE | 未激活的原子安装临时目录 |
| 已验证的 `staging/download-cache` Python 安装器 | REVIEW_REQUIRED | 可加速重试，但会占用额外空间 |
| `advanced-ai/envs/<active>`、`advanced-ai/models/<active>` | KEEP | 当前激活环境与唯一模型副本 |
| `components.previous.json` 指向的上一版本 | KEEP | 回滚所需 |
| 未被 active/previous 引用的旧环境 | REVIEW_REQUIRED | 确认无需回滚后可清理 |
| `desktop/src-tauri/target/`、`runtime-build*/` | REBUILDABLE | 编译缓存和构建中间产物 |
