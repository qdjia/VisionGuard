# VisionGuard Windows 分发架构

## 当前结论

Phase 16 最终选择 **Tauri v2 轻量 NSIS 按用户安装 + GPU Runtime 独立导入 + 模型独立导入**。

不采用约 9 GiB 的单体安装器。当前 PyInstaller Runtime 为 `5,311,923,777` 字节，模型目录为 `4,418,141,986` 字节；把二者绑定会让每次桌面端更新都重复分发模型，并显著增加安装失败和回滚成本。实际把 Runtime 交给 NSIS 时，`makensis` 在约 1.91 GB 的 mmap 阶段报内部编译错误，因此原先优先评估的“App + Runtime 安装器”已被实测否决，而不是停留在理论判断。

当前生成的是 `0.1.0-rc.*` 本地候选包，不是可以公开上传的 v1.0 正式版。公开发行门禁见本文末尾。

当前实测：Desktop 主程序约 16.7 MiB，轻量离线安装器约 209.7 MiB，Runtime 安装目录约 4.95 GiB，模型目录约 4.12 GiB，安装后的核心组件合计约 9.08 GiB。下载包与安装文件同时保留并加 15% 余量时，建议至少准备 22 GiB 可用磁盘空间。

## 方案比较

| 方案 | 用户体验 | 更新成本 | 离线能力 | 当前结论 |
|---|---|---|---|---|
| A. App + Runtime + Models 单体包 | 一次安装 | 任何改动都重下约 9 GiB | 最强 | 拒绝，过大且耦合 |
| B. App + GPU Runtime；模型独立 | 首次启动选择模型包 | App 与模型可独立更新 | 完整 | NSIS 大文件实测失败 |
| C. App、Runtime、Models 三包 | 首次启动分两步导入 | 最低 | 完整 | **采用** |
| D. CPU/GPU 双 Runtime | 选择复杂 | 双倍维护 | 完整 | CPU VLM 当前不实用，暂不构建 |

Tauri 官方支持 NSIS 和 MSI。NSIS 的 `currentUser` 模式无需管理员权限，安装在 LocalAppData 范围，并原生提供 Start Menu 与安装完成页的桌面快捷方式选项。VisionGuard 使用 NSIS，避免维护第二套安装器。

## 磁盘与版本边界

```text
按用户安装位置（由 Tauri/NSIS 管理，只读应用内容）
├── VisionGuard.exe
├── LICENSE
└── THIRD_PARTY_NOTICES.md

Tauri app_local_data_dir（可写用户数据）
├── runtime-components/
│   ├── runtime-v0.1.0/
│   │   ├── visionguard-runtime.exe
│   │   ├── _internal/
│   │   └── runtime-manifest.json
│   ├── active.json
│   └── active.previous.json
├── models/
│   ├── models-v1/
│   ├── models-v2/               # 未来版本，可并存
│   ├── active.json
│   └── active.previous.json
├── runtime/                     # 每次运行的配置与握手文件
├── logs/
├── artifacts/
├── cache/
└── settings/
```

按用户安装不会写入 `Program Files`。无论最终由 NSIS 选择哪个 LocalAppData 应用目录，Runtime、模型、日志、缓存和产物都写入 Tauri 的 `app_local_data_dir`。卸载器删除 Desktop 与快捷方式；Runtime、模型和用户数据默认保留，以便重装和升级复用。

版本相互独立：

- Desktop App：SemVer，当前 `0.1.0`；
- Runtime：SemVer，当前 `0.1.0`；
- Model Bundle：`models-v1`；
- Pipeline / Routing / Fusion / Prompt：分别记录在 release manifest 与 `/v1/meta`。

## 首次运行和模型安装

```text
Launch
  → RuntimeManager 查找 runtime-components/active.json
  → 未找到有效 Runtime
  → Runtime Setup（安全解压、逐文件 SHA-256、原子激活）
  → RuntimeManager 查找 models/active.json
  → 未找到有效模型
  → Model Setup
  → 用户选择 .zip 或已解压目录
  → 检查 manifest / Runtime 兼容范围 / 磁盘空间
  → 拒绝绝对路径、..、符号链接和 Zip Slip
  → 复制或解压到 models-v1.installing-<uuid>
  → 全量验证文件大小与 SHA-256
  → 保留损坏的同名旧目录为 *.invalid-<uuid>
  → rename 为 models-v1
  → 原子更新 active.json（失败时恢复 previous pointer）
  → 启动 Runtime
  → Ready
```

安装前按解压后体积另加 15% 安全余量检查空间。安装失败清理 staging，不覆盖已验证的模型。目录导入也拒绝符号链接，避免复制时逃逸到来源目录之外。

## GPU 与离线策略

第一版仅生成 Windows x86_64 GPU Edition。Runtime 在构造模型之前检查：

- 64 位 Windows；
- PyTorch 能否发现 CUDA GPU；
- GPU 名称、CUDA 版本和显存总量（诊断信息）；
- Runtime 用户数据盘剩余空间；
- Model Bundle 与 Runtime 版本兼容性。

当前实测环境是 RTX 4060 Laptop GPU 8 GiB、驱动 `580.97`、PyTorch CUDA `12.8`。这只是通过测试的配置，不是最低要求。最低显存和内存必须通过多台硬件重复测量后确定。

运行时强制 Hugging Face、Transformers、Datasets、Paddle 和 YOLO 使用离线配置。安装器选择 WebView2 offline installer，使安装阶段也不需要下载 WebView2；代价是安装包增加约 127 MB。

## Release Builder

```powershell
python scripts/build_release.py --version 0.1.0-rc.1
python scripts/validate_release.py release/v0.1.0-rc.1
python scripts/validate_release.py release/v0.1.0-rc.1 --public
```

第一条命令构建 Runtime、前端、轻量 Tauri NSIS、Runtime ZIP、模型 ZIP、`SHA256SUMS.txt`、`release-manifest.json` 和 `RELEASE_NOTES.md`。生成内容位于 Git 忽略的 `release/`。

普通验证只证明本地候选包内部一致。`--public` 还会检查每个资产是否允许公开、是否小于 GitHub 单资产 2 GiB 限制，以及 manifest 是否解除全部发行门禁。当前它应当失败。

## 升级、重装和卸载

- Desktop 更新由 NSIS 替换安装目录中的应用文件；
- Runtime 使用独立版本目录与 active pointer，不由 NSIS 覆盖；
- 模型位于 app local data，不随应用替换；
- 新模型先安装为新目录，验证完成后才更新 pointer；
- 卸载默认保留 runtime-components、models、logs、artifacts、cache 和 settings；
- 重装后 RuntimeManager 自动读取 `active.json`；
- 单实例插件聚焦已有窗口，阻止第二套 GPU Runtime 被加载；
- Tauri NSIS 会在安装/卸载时检测正在运行的应用，Runtime 又由 Desktop 窗口生命周期负责关闭。

## 仍需人工完成的发行门禁

1. Ultralytics/YOLO 再分发方式未解决；
2. NVIDIA CUDA Runtime 随 PyTorch 打包的再分发条款未完成法律核验；
3. Windows 安装器尚未代码签名；
4. 当前环境不能替代 Windows Sandbox/干净 VM；
5. 安装、快捷方式、卸载、重装、升级和完整 GUI 必须在候选安装器上人工验收；
6. 模型 ZIP 与 Runtime ZIP 均超过 GitHub 单资产 2 GiB 限制；分卷/外部托管方案应在许可解除后再定稿；
7. Runtime review/meta/ready 的 session token 仍未迁移到 Rust HTTP proxy，保留为后续安全加固项。

只有这些门禁解除，`release-manifest.json` 的 `public_release_ready` 才能改为 `true`。
