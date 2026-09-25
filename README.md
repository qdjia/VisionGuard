# VisionGuard

> 基于视觉语言模型的多模态出版内容智能审校系统<br>
> Multimodal Publishing Content Moderation System Based on Vision-Language Models

VisionGuard 是面向 AI / Computer Vision 算法实习作品集的本地优先项目。系统将目标检测、OCR、传统文本分类、动态路由、视觉语言模型与风险融合组织为可评估、可解释、可服务化的完整推理链路。

> 当前处于 **v1.0 Release Candidate 准备阶段**。仓库尚未提供可公开下载的正式安装包，也未发布 `v1.0.0-rc.1` Tag。本地构建成功不代表已获准公开发行。

## 产品边界

VisionGuard is a local-first desktop AI application. Internet access may be required for installation, model acquisition, and component updates, while all image review and AI inference run locally on the user's machine without cloud inference APIs.

- 安装、模型/组件获取和更新可以使用网络。
- 实际审核推理在用户本机完成：Detector、OCR、Baseline、Router、VLM、Fusion 和结构化结果均不依赖云端推理 API。
- 审核图片在推理期间由本地 Runtime 处理；项目不提供向云端审核服务上传图片的实现。
- “本地推理”不等同于“完全离线”：项目不承诺零网络流量、隔离网运行或安装阶段断网可用。

## 能力

- **Fast Review**：使用 CPU Core 完成目标检测、OCR、文本基线、动态路由和风险融合。
- **Deep Review**：安装可选 Advanced AI 后，按需调用本地 VLM 处理复杂语义或冲突证据。
- **结构化结果**：输出风险等级、类别、证据、置信度、人工复核建议和分阶段耗时。
- **工程评估**：包含训练、评估、批量推理、性能分析、错误分析、SBOM 和发行校验工具。

## 组件

| 组件 | 必需 | 当前实测体积 | 作用 |
|---|---:|---:|---|
| Slim Core Runtime | 是 | 约 0.697 GiB | ONNX Detector、PaddleOCR、Baseline、Routing、Fusion |
| Core Models | 是 | 约 0.146 GiB | Core 模型资产 |
| VLM Runtime | 否 | 约 4.216 GiB | PyTorch、Transformers、CUDA 侧运行环境 |
| VLM Models | 否 | 约 3.974 GiB | Qwen3-VL-2B-Instruct 模型资产 |

Core-only 安装体积约 0.843 GiB。Advanced AI 采用独立分卷、SHA-256 校验和原子激活，不会因 VLM 故障影响 Fast Review。

## 计划中的安装体验

1. 下载并校验 `VisionGuard-Setup-<version>.exe`。
2. 安装并启动内置 Slim CPU Core。
3. 如需 Deep Review，在应用内获取或导入 `advanced-ai-manifest.json`。
4. VisionGuard 校验分卷和磁盘空间，安装并激活本地 VLM Runtime 与模型。

最终用户不需要安装 Python、Conda、Node 或 Rust。

## 系统要求与限制

- 目标平台：64 位 Windows。
- Core：CPU 模式；最低内存与性能仍需多机验证。
- Advanced AI：当前只在 RTX 4060 Laptop 8 GiB 上完成开发验证，这不是最低配置承诺。
- Clean Windows、真实 GUI 安装生命周期和历史真实图片回归仍待独立环境验收。
- Windows RC 计划为未签名包，可能出现 SmartScreen 提示。
- Ultralytics Detector 在 AGPL 开源发行路径下为 `ALLOWED_WITH_CONDITIONS`；发布时必须同时满足源码、许可证、构建脚本、来源记录及发行版本映射条件。
- NVIDIA `nvJitLink_120_0.dll` 再分发映射仍为 `UNCLEAR`，继续阻塞公开 RC。

当前门禁见 [Release Gate](docs/release_gate.md)，硬件记录见 [Hardware Compatibility](docs/hardware_compatibility.md)。

## 架构

```mermaid
flowchart LR
    I[输入图片] --> D[YOLO / ONNX Detector]
    I --> O[PaddleOCR]
    O --> B[TF-IDF + GBDT]
    D --> R[Dynamic Routing]
    O --> R
    B --> R
    R -->|证据明确| F[Risk Fusion]
    R -->|不确定 / 冲突 / 高风险| V[Local VLM Runtime]
    V --> F
    F --> J[Structured Review Result]
```

```text
VisionGuard Desktop
├── bundled Slim CPU Core
│   ├── Core Runtime
│   └── Core Models
└── optional Advanced AI
    ├── VLM Runtime parts
    └── VLM Model parts
```

详细设计见 [架构说明](docs/architecture.md)、[组件化 Runtime](docs/componentized_runtime.md) 和 [Desktop 架构](docs/desktop_architecture.md)。

## 目录

```text
src/visionguard/       Python 算法、Pipeline、评估与 API
desktop/               Tauri + React 桌面应用
configs/               可版本化配置
scripts/               训练、评估、构建、验收工具
packaging/             Runtime 与组件发行配置
tests/                 Python 单元与集成测试
docs/                  架构、实验、发行和验收记录
artifacts/              本地实验产物（不提交）
models/                 本地模型包（不提交）
```

## 开发

```powershell
conda activate visionguard
pip install -e ".[dev]"

cd desktop
npm ci
```

质量检查：

```powershell
pytest -q
ruff check .
ruff format --check .
python -m compileall src scripts

cd desktop
npm test
npm run lint
npx tsc -b
npm run build

cd src-tauri
cargo test
cargo fmt --check
cargo check
```

生成 SBOM：

```powershell
python scripts/generate_sbom.py --version 1.0.0-rc.1 --output artifacts/sbom
```

最终 RC 构建和校验命令为：

```powershell
python scripts/build_release.py --version 1.0.0-rc.1
python scripts/validate_release.py --rc
```

只有严格校验、clean-machine、GUI 生命周期、升级/回滚/卸载/重装、历史回归与许可证分发门全部通过，才可建议创建 `v1.0.0-rc.1`。真实离线测试不是 v1.0 的产品要求，也不是 RC 阻断项。

## 许可证

VisionGuard 自有代码以 **GNU Affero General Public License v3.0 only (`AGPL-3.0-only`)** 发行。AGPL 是自由/开源许可证，不是“禁止商业使用”许可证；分发或通过网络提供修改后的适用程序时，应遵守相应源码提供义务。

第三方代码、Runtime、模型和资产继续适用各自许可证，根许可证不会重新许可它们。详见 [LICENSE](LICENSE)、[NOTICE](NOTICE)、[Third-Party Notices](THIRD_PARTY_NOTICES.md)、[发行许可报告](docs/release_licenses.md) 和 [AGPL 迁移记录](docs/agpl_migration.md)。
