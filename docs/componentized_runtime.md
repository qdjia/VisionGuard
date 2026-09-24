# Componentized Local AI Runtime

VisionGuard 的发行边界分为必需的 Desktop、Core Runtime、Core Models，以及可选的 VLM Runtime、VLM Models。Core 负责 Detector ONNX、OCR、Baseline、Routing、Fusion 与 `/v1/review`；VLM Runtime 只负责 Qwen3-VL 的 lazy load、prompt、结构化生成和 `ModerationResult` 校验。

## 调用链

Desktop 启动 Core 后即可进入 Ready。若 Advanced AI 组件存在，Desktop 再启动轻量 VLM 进程；VLM 在 `127.0.0.1:0` 发布动态 endpoint，但不加载模型。Desktop 使用 Core control token 注册 endpoint 与独立 VLM session token。首次 Deep Review 或路由命中 VLM 时加载一次模型，后续请求复用相同进程和模型。

Core 内的 `RemoteVLMProvider` 是唯一 transport adapter。Routing 与 Fusion 不感知 HTTP、端口或 sidecar。VLM 崩溃或超时时，当前结果保持 partial/manual-review，Core 和 Fast Review 继续可用。

## 合同与安全

- VLM API major：`1`
- API：`GET /health/live`、`GET /health/ready`、`GET /v1/meta`、`POST /v1/analyze`
- 图片：loopback multipart，不用 Base64
- 内容：`VLMContext`、`ModerationPolicy`、prompt version 和 request metadata
- 输出：经 Pydantic 与 policy 校验的 `ModerationResult`；raw generation 不离开 VLM 进程
- 绑定：仅 `127.0.0.1`
- 鉴权：每次进程启动生成新的随机 session token，经 `X-VisionGuard-Session` 传递；Core 注册接口另受 Core control token 保护

## Lazy load 选择

采用“进程预启动、模型 lazy load”。与完全按需 spawn 相比，它占用少量空闲内存，但显著简化动态端口发现、Core 注册、崩溃监测和第一次请求的进程启动抖动。模型加载仍不阻塞 Core Ready，且 `model_init_count` 可验证连续请求只初始化一次。

## 组件布局与大资产

建议用户数据布局：

```text
components/
  core-runtime/
  core-models/core-models-v1/
  vlm-runtime/
  vlm-models/vlm-models-v1/
```

VLM 模型约 3.974 GiB，不能作为单个 GitHub 大文件资产。`scripts/split_release_asset.py` 生成有序 part 和总文件/分卷 SHA-256 manifest；安装器必须自动校验、拼装到临时目录，再原子切换 active pointer，不能要求用户手工合并。Phase 18 未把该策略误报为已经完成的公开托管方案。

## 构建

```powershell
python scripts/build_runtime.py --profile core
python scripts/build_runtime.py --profile vlm
python scripts/build_model_bundle.py --profile core --bundle-version core-models-v1 --output models/core-models-v1
python scripts/build_model_bundle.py --profile vlm --bundle-version vlm-models-v1 --output models/vlm-models-v1
```
