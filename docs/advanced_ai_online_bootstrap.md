# Advanced AI 在线引导安装

## 发行边界

默认 GitHub Release 只包含 Desktop、Slim CPU Core、Core Models、固定 bootstrap manifest 和小型 VisionGuard VLM Python wheel。它不包含 PyTorch wheel、Qwen 权重或 CUDA/NVIDIA DLL。旧 PyInstaller VLM Runtime 与分卷构建脚本保留为 legacy/fallback/reference，不是默认发行路径。

安装联网、推理本地。用户点击安装后，VisionGuard 才会从固定官方 HTTPS 来源下载组件；完成安装后，图片、OCR、检测结果、策略和 VLM 请求只在本机进程与 loopback API 间流动。

## 固定供应链

- Python 3.11.9 x64：python.org 官方 embeddable ZIP，固定大小和 SHA-256；pip 由固定 SHA-256 的 PyPA 官方 `get-pip.py` 引导。该方案不写全局 PATH/注册表，也不会升级用户已有的同 minor Python。
- PyTorch 2.11.0+cu128 / TorchVision 0.26.0+cu128：`download.pytorch.org/whl/cu128`。
- 其余 VLM 依赖：固定版本，仅从 PyPI 官方 simple index 获取。
- 模型：`Qwen/Qwen3-VL-2B-Instruct`，固定 commit `89644892e4d85e24eaac8bacfd4f463576704203`，下载到 VisionGuard 私有目录，不使用全局 HF cache。
- VisionGuard VLM 代码：构建时生成无 Core 依赖声明的专用小型 wheel，安装时使用
  `--no-deps` 放入受管环境。YOLO、PaddleOCR、OpenCV 与传统基线不会因此进入独立 VLM
  环境；VLM 的锁定依赖由 bootstrap 清单逐项安装，并最终通过 `pip check` 验证。

生产 UI 不接受任意 URL、包名、版本、Python 路径或 Hugging Face repo。所有外部程序均通过参数数组启动，不经过 shell。

安装前通过 `nvidia-smi` 检查 NVIDIA GPU、驱动版本与显存并写入状态记录。当前只验证过
RTX 4060 Laptop 8 GiB，不据此虚构通用最低显存；无法确认 NVIDIA 配置时安装会以
`GPU_REQUIREMENT_NOT_SATISFIED` 安全失败，Core 仍可使用。

## 状态与目录

状态机为 `NotInstalled → Preparing → DownloadingRuntime → CreatingEnvironment → InstallingDependencies → DownloadingModel → Validating → Ready`，失败进入 `Failed`，不会改写 active registry。更新和移除分别使用 `Updating`、`Removing`。

```text
app_local_data_dir/
├── advanced-ai/
│   ├── envs/vlm-v1/
│   ├── models/vlm-models-v1/
│   ├── cache/huggingface/
│   ├── staging/download-cache/
│   ├── advanced-ai-env.json
│   └── advanced-ai-installed-bom.json
└── components/
    ├── components.json
    └── components.previous.json
```

只有 Python、依赖、模型文件、导入检查和版本检查全部通过后，才原子替换 `components.json`。VLM 仍是独立进程，由桌面端用受管 `python.exe -m visionguard.vlm_runtime`、动态端口与一次性 session token 启动；Core 仍只看 `RemoteVLMProvider`。

模型的 `.incomplete` 文件保存在持久 download-cache 中。网络中断时只清理当次临时 Python
环境，不删除已下载的模型字节；重试会从断点继续，完整校验通过后才移动到原子激活目录。

## SBOM 边界

Release SBOM 只描述安装器实际分发的内容，不把安装时下载的 PyTorch/CUDA 或模型伪装成安装器内容。成功安装后生成 `advanced-ai-installed-bom.json`，记录实际环境包版本和模型 revision；该文件不包含 token 或凭据。

## 当前验证限制

自动化测试覆盖 manifest 信任边界、固定版本、磁盘/GPU 预检、HTTP Range 断点续传、
断网安全失败、原子激活和托管启动解析。开发机上的受管 Python、CUDA、动态端口、session
token、两次真实 Deep Review、结构化输出与 `model_init_count = 1` 已通过；该 Deep Review
使用了与固定 revision 大小及 SHA-256 一致的已有模型副本，不能替代 fresh-download 验收。
官方 Hugging Face 链路在完整权重下载中多次超时/重置，虽已真实验证断点从 88 MiB 继续到
216 MiB，完整下载仍未完成。clean Windows GUI 生命周期和历史真实图片回归也仍待发布门禁
实测，因此当前 online-bootstrap gate 保持 BLOCKED。
