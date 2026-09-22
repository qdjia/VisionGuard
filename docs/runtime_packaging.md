# VisionGuard Runtime 打包说明

## 方案选择

Phase 15 使用 PyInstaller one-folder，而不是 one-file 或 Nuitka。

- one-folder 启动时无需把 5 GiB 级依赖解压到临时目录，故障也更容易定位；
- PyInstaller 能直接复用当前已验证的 Conda 环境，不要求额外 C/C++ toolchain；
- Nuitka 适合作为后续体积和启动性能优化实验，但当前引入编译器和大量兼容验证会扩大阶段范围；
- 模型不打进 Runtime，避免仅更新权重时重建 Python 运行环境。

## 可提交与生成目录

```text
packaging/
├── runtime/visionguard-runtime.spec       # 提交：可复现打包规则
├── runtime/requirements-build.txt         # 提交：打包器版本
└── models/manifest.template.json          # 提交：manifest 示例

runtime-dist/visionguard-runtime/           # 忽略：PyInstaller one-folder
├── visionguard-runtime.exe
└── _internal/
    └── resources/{configs,prompts}/

models/models-v1/                           # 忽略：真实模型包
├── manifest.json
├── detector/
├── ocr/
├── baseline/
└── vlm/

desktop/src-tauri/binaries/                 # 忽略：Tauri 暂存产物
├── visionguard-runtime-x86_64-pc-windows-msvc.exe
├── _internal/
└── runtime_build.json
```

## 一键构建

在项目的 `visionguard` Python 环境中执行：

```powershell
python scripts/build_model_bundle.py --hardlink --force
python scripts/build_runtime.py
```

`--hardlink` 只用于本机构建阶段节省磁盘；发布介质必须复制完整独立文件。`build_runtime.py` 会清理限定的生成目录、运行 spec、读取 Rust host triple、暂存 Tauri Sidecar，并生成不含用户名和绝对路径的 `runtime_build.json`。

## Runtime 入口与配置

稳定入口为 `visionguard.runtime.main:main`，命令行仅接受：

```text
visionguard-runtime.exe --config <absolute-path> --status-file <absolute-path>
visionguard-runtime.exe --config <absolute-path> --status-file <absolute-path> --validate-only
```

Rust 在应用本地数据目录生成每次启动独立的 JSON 配置和状态文件。配置指定模型包、日志、cache、artifact、并发数与校验强度；不包含 control token。token 仅经子进程环境变量传递，Python 读取后立即从环境映射移除。

## 模型校验

`scripts/build_model_bundle.py` 依据本机已验证的 YOLO、PaddleOCR、baseline 与 Qwen 路径创建版本化包。manifest 路径必须是安全的 POSIX 相对路径。

- `quick`：检查 manifest、必需组件、文件类型和字节数，适合每次启动；
- `full`：额外逐文件计算 SHA-256，适合构建/安装验收；
- Runtime 版本必须落在 `min_inclusive <= version < max_exclusive`。

缺失、损坏和版本不匹配会写入结构化状态，而不是把 `FileNotFoundError` 或 traceback 直接呈现给用户。

## 动态端口、readiness 与退出

Runtime 自行绑定 `127.0.0.1:0` 并把已占用 socket 交给 Uvicorn，随后原子发布 endpoint。Tauri 依次等待：

```text
status handshake → /health/live → /health/ready → /v1/meta compatibility
```

模型加载在一个 Runtime 进程中完成一次。桌面关闭时先请求受 control token 保护的本地 shutdown；5 秒内未退出才 force kill。非预期退出通过 Sidecar event stream 反映到 Runtime Setup UI。

## 验证命令

只验证独立可执行文件和模型包，不启动模型服务：

```powershell
python scripts/smoke_test_packaged_runtime.py --validate-only
```

真实启动、live/ready/meta、安全图片 review 和 graceful shutdown：

```powershell
python scripts/smoke_test_packaged_runtime.py --timeout 300
```

Rust fake-runtime 测试覆盖动态端口、spawn/live、readiness、启动超时、异常退出、restart、graceful stop、force-stop fallback、endpoint 注入和无孤儿监听：

```powershell
cargo test --manifest-path desktop/src-tauri/Cargo.toml
```

完整哈希可在 Runtime 配置中将 `model_validation` 改为 `full`。离线验证时应先断开外网或在防火墙中阻断进程，再运行真实 smoke；Runtime 已强制 Hugging Face 离线并显式指定所有模型路径。

## 当前实测基线（Windows x86_64）

2026-09-21 使用 Python 3.11、PyInstaller 6.22.3 构建：

| 项目 | 大小 |
|---|---:|
| Runtime one-folder | 5,311,923,777 bytes（约 4.95 GiB） |
| Model bundle models-v1 | 4,418,141,986 bytes（约 4.11 GiB） |

Runtime 中约 4.0 GiB 来自 CUDA PyTorch。此数字是首个可工作的发布基线，不是假装优化后的指标。本机完整 cold start、全部组件 ready、安全图片 review 与 graceful shutdown 共 35.25 秒；构建机和显卡不同会明显变化。

### PaddleOCR 冻结兼容

PaddleOCR/PaddleX 在冻结环境中仍会通过包元数据定位 OCR 核心依赖，并在 Windows 上动态加载 `paddle/libs` 下的计算库。PyInstaller spec 因此显式收集这些 distribution metadata 与全部 Paddle DLL。Runtime 还提供最小离线 ModelScope 兼容层，只满足 PaddleX 的启动期导入；任何模型下载入口都会明确失败，避免发布包在用户机器上静默联网。

## 故障定位

- Runtime 日志：Tauri 应用本地数据目录下 `logs/visionguard-runtime.log`，10 MiB 轮转并保留 3 份；
- 状态文件：`runtime/status-<run-id>.json`，只包含去敏状态；
- `MODEL_BUNDLE_MISSING`：模型目录或 manifest 不存在；
- `MODEL_BUNDLE_INVALID`：结构、大小或哈希错误；
- `RUNTIME_NOT_READY`：模型初始化异常或超时；
- `RUNTIME_VERSION_MISMATCH`：App、Runtime 或模型兼容范围不一致。

不要把生成二进制、权重、日志或状态文件提交到 Git。

## 已知限制

- PyInstaller 会包含 PaddleX 和 CUDA PyTorch 的较大依赖闭包；Phase 16 采用独立 Runtime ZIP，尚未完成 CUDA/Paddle 依赖裁剪；
- 发布模式由首次启动安装器把已校验的 Runtime 与模型分别激活到应用数据目录；开发模式仍可从仓库生成目录回退；
- Runtime 不再内嵌进 NSIS。应用通过活动版本指针启动独立 Runtime，避免 NSIS 对超大文件映射失败；
- shutdown control 面受 token 保护，但审核接口仍为 loopback-only，无逐请求 session token；
- smoke 脚本默认审核 `data/vlm_eval/safe.png`；只验证生命周期时可加 `--skip-review`；
- Windows 平台产物必须在 Windows 上构建，PyInstaller 不是跨平台编译器。
