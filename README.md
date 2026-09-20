# VisionGuard

基于视觉语言模型的多模态出版内容智能审校系统。

本项目面向 AI / Computer Vision 算法作品集，采用 YOLO、OCR、规则引擎与 VLM
组成多阶段级联推理流水线。当前开发到 **Phase 11：Systematic Error Analysis**。

## Systematic Error Analysis（Phase 11）

Phase 11 consumes existing evaluation records and ground-truth manifests offline. It separates
observable failures from suspected causes, preserves a non-causal propagation trace, and never
changes routing, fusion, prompt, policy, threshold, or model weights automatically. The tracked
hard-case manifest is an engineering regression seed, not a production publishing benchmark.

```bash
# Offline analysis; YOLO/OCR/VLM are not loaded.
python scripts/analyze_pipeline_errors.py \
  --records artifacts/fusion/evaluation_phase9_20260917/records.jsonl \
  --config configs/error_analysis.yaml \
  --output artifacts/error_analysis/phase11_analysis_v1

# Hash-deduplicated hard-case manifest.
python scripts/build_hard_case_dataset.py \
  --errors artifacts/error_analysis/phase11_analysis_v1/error_cases.jsonl \
  --output data/hard_cases/manifest.jsonl

# Replay only routing and fusion over stored signals.
python scripts/replay_error_cases.py \
  --records artifacts/fusion/evaluation_phase9_20260917/records.jsonl \
  --output artifacts/error_analysis/phase11_replay_v1

# Live regression explicitly loads the configured models.
python scripts/run_hard_case_regression.py \
  --manifest data/hard_cases/manifest.jsonl \
  --pipeline-mode cascaded \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/error_analysis/phase11_regression_v1

python scripts/generate_error_report.py \
  --analysis artifacts/error_analysis/phase11_analysis_v1 \
  --output artifacts/error_analysis/phase11_analysis_v1/report_copy.md
```

The extended manifest accepts partial `ground_truth` (`risk_level`, `categories`, `text`,
`objects`, `requires_manual_review`) and annotation metadata (`source`, `difficulty`,
`annotation_status`, `notes`, `generation_method`). Missing transcription or object boxes disables
CER or detector FP/FN claims respectively. Use `verified`, `needs_review`, or `ambiguous` annotation
status; model output must never be promoted to ground truth.

Each new analysis directory contains `config.yaml`, `summary.json`, `failure_taxonomy.csv`,
`error_cases.jsonl`, `hard_cases.jsonl`, `top_errors.md`, `recommendations.json`, the main report,
and per-case traces/visualizations. Existing non-empty output directories are rejected. The current
three-sample Phase 9 evaluation only validates the engineering flow and is explicitly too small for
quality claims; a production conclusion requires a diverse, independently annotated 20–50+ sample
evaluation set at minimum.

## 安装与测试

```bash
python -m pip install -e ".[dev]"
pytest
```

### OpenCV 单一发行包

当前 PaddleOCR / PaddleX 的 OCR 依赖固定使用 `opencv-contrib-python==4.10.0.84`，
它包含本项目和 YOLO 所用的 OpenCV 基础功能。不要同时安装普通版、headless 版与
contrib 版：它们都写入同一个 `cv2` 目录，卸载任意一个可能损坏其他版本。

Ultralytics 的上游依赖仍按包名要求 `opencv-python`，因此常规安装可能重新引入普通版。
在安装项目依赖后，使用当前项目的 Python 执行以下步骤，以恢复单一 contrib 版本：

```bash
python -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python opencv-contrib-python-headless
python -m pip install --no-deps opencv-contrib-python==4.10.0.84
python -c "import cv2; print(cv2.__version__, cv2.__file__)"
pytest
```

此方案有一个明确的包装层限制：`pip check` 会报告 Ultralytics 缺少 `opencv-python`，
即使 `cv2` 基础功能已由 contrib 提供。项目不修改上游元数据或伪造占位包来隐藏该提示；
安装或升级 Ultralytics 后需要再次执行上述清理，并进行真实 YOLO / OCR smoke test。
模型权重不受此清理影响。

加载默认配置：

```python
from visionguard.config import load_config

config = load_config("configs/default.yaml")
print(config.detection.class_names)
```

## 单图检测

将兼容 Ultralytics 的 YOLO26 权重放在 `checkpoints/yolo26.pt`，然后运行：

```bash
python scripts/infer_detector.py \
  --image data/examples/test.jpg \
  --config configs/detector.yaml \
  --output artifacts/inference/test_result.jpg
```

真实权重 smoke test（连续推理两次以确认实例复用并观察 warmup 后延迟）：

```bash
python scripts/smoke_test_detector.py \
  --image data/examples/test.jpg \
  --config configs/detector.yaml
```

三通道 `numpy.ndarray` 输入约定为 OpenCV BGR；四通道数组约定为 RGBA，并转换为
BGR。模型在 `YOLODetector` 构造时加载一次，后续 `predict()` 复用同一实例。

## 数据集与训练

标准数据集结构：

```text
data/visionguard/
├── images/{train,val,test}/
└── labels/{train,val,test}/
```

标注行格式为 `class_id x_center y_center width height`，坐标归一化到 `[0, 1]`。
类别只在 dataset YAML 中定义。

```bash
python scripts/validate_dataset.py --data configs/datasets/visionguard.yaml
python scripts/train_detector.py --config configs/train_detector.yaml
```

断点续训：

```bash
python scripts/train_detector.py \
  --config configs/train_detector.yaml \
  --resume artifacts/experiments/yolo26n_baseline_640/weights/last.pt
```

独立评估和轻量错误分析：

```bash
python scripts/evaluate_detector.py \
  --checkpoint artifacts/experiments/yolo26n_baseline_640/weights/best.pt \
  --data configs/datasets/visionguard.yaml --split val

python scripts/export_error_cases.py \
  --checkpoint artifacts/experiments/yolo26n_baseline_640/weights/best.pt \
  --data configs/datasets/visionguard.yaml \
  --experiment-name yolo26n_baseline_640
```

## GPU smoke test

```bash
python scripts/create_smoke_dataset.py
python scripts/validate_dataset.py --data configs/datasets/visionguard_smoke.yaml
python scripts/train_detector.py --config configs/train_detector_smoke.yaml
```

该数据集是流水线测试用合成矩形，不用于评价模型精度。

## 增强与复现

默认增强使用 Ultralytics 原生 HSV、轻微旋转、平移、缩放、水平翻转和低概率 Mosaic。
垂直翻转、透视和 MixUp 默认关闭，避免破坏出版页面方向、文字、二维码和符号语义。
Albumentations 仅作为后续扫描噪声、模糊和印刷退化实验的可选扩展，本阶段不重复执行
YOLO 已有增强。

`deterministic: true` 会固定 Python、NumPy、PyTorch 和 CUDA 随机状态，有利于复现，
但可能降低训练吞吐。CPU 训练会自动关闭 AMP。

## Baseline 配置

| Model | Image size | Batch | Epochs | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| YOLO26n | 640 | 8 | 100 | 待真实数据集训练 | 待训练 | 待训练 | 待训练 |

## OCR

Phase 4 使用 PaddleOCR 3.x adapter，并通过稳定的 Pydantic Schema 返回文本、置信度、
倾斜四点 polygon、axis-aligned bbox、原始/过滤后文本块数量和分阶段耗时。模型在
`OCREngine` 构造时只加载一次，全图与 ROI 共用同一个实例。ROI 内坐标会映射回原图。

PaddleOCR 首次运行会下载模型到 `artifacts/paddlex_cache/`。`device: auto` 会根据当前
PaddlePaddle 构建自动选择设备；本项目允许 PyTorch YOLO 使用 GPU、PaddleOCR 使用 CPU。

全图 OCR 与可视化：

```bash
python scripts/infer_ocr.py \
  --image data/examples/page.jpg \
  --config configs/ocr.yaml \
  --output artifacts/ocr/page_result.jpg
```

ROI OCR（输出坐标仍是原图坐标）：

```bash
python scripts/infer_ocr_roi.py \
  --image data/examples/page.jpg \
  --bbox 100 200 800 500 \
  --config configs/ocr.yaml \
  --output artifacts/ocr/page_roi_result.jpg
```

真实模型 smoke test：

```bash
python scripts/create_ocr_smoke_images.py
python scripts/smoke_test_ocr.py \
  --chinese-image data/ocr_smoke/chinese.png \
  --english-image data/ocr_smoke/english.png
```

CER 评估清单为 JSONL，每行包含相对清单目录的 `image` 和 `text`：

```json
{"image":"001.jpg","text":"这是正确文本"}
```

```bash
python scripts/evaluate_ocr.py \
  --manifest data/ocr_eval/ground_truth.jsonl \
  --output artifacts/ocr/evaluation.json \
  --error-threshold 0.3
```

高 CER 图片及其 GT、Prediction、CER 会导出到 `artifacts/ocr/error_cases/`。

## 阶段边界

当前已实现配置与 Schema、YOLO26 单图推理、YOLO 数据集/训练/评估、PaddleOCR
全图/ROI 推理和 CER 基础评估、传统文本 Baseline、独立 VLM Adapter、同步多模态 Review
 Pipeline、规则式级联推理、动态路由、可解释多模态 Risk Fusion 和可复现性能 Benchmark。尚未实现
跨阶段综合 Error Analysis 或 FastAPI。

## 传统文本审核 Baseline

`OCR full_text → 清洗 → character TF-IDF → GBDT → normal / sensitive`。
这仅是后续与 VLM 比较的传统方法基准，不是最终审核模型。
中文 character 2～4 gram 不依赖分词，可捕获局部字符组合、新词和部分变体；但它不具备
长距离语义、上下文意图或视觉理解能力。GBDT feature importance 也不是因果语义解释。

数据为 UTF-8 CSV：`text,label`，0=normal、1=sensitive，可附加 category（当前不参与训练）。
清洗包括 NFKC、换行/空白标准化、格式控制字符清理和可选 lowercase；空文本去除、
重复文本去重、重复文本标签冲突报错，不同 split 清洗后重叠报错。
推理遇到空文本会明确报错，不将空白 OCR 擅自判为 normal。

提供 `data/text_moderation/sample/{train,val,test}.csv` 共 36 条自构造文本，仅验证工程流程，
不可将其指标作为真实审核精度。真实/private 数据和模型不提交 Git。

```bash
# 可选：单文件固定 seed 分层划分 70/15/15，不覆盖已有输出
python scripts/split_text_dataset.py --data data/private/all.csv --output data/text_moderation/custom --seed 42

# 默认 sample 训练；配置可覆盖 threshold/max-features/seed，并保存完整配置
python scripts/train_text_baseline.py --config configs/baseline_text.yaml

python scripts/infer_text_baseline.py --text "这是正常出版教材内容"
python scripts/infer_text_baseline.py --texts-json data/private/texts.json

# test 独立评估
python scripts/evaluate_text_baseline.py --data data/text_moderation/sample/test.csv

# 仅在 val 分析阈值，不自动修改正式 threshold
python scripts/evaluate_text_baseline.py --data data/text_moderation/sample/val.csv --threshold-sweep --output artifacts/baseline/char_2_4_gbdt_sample_v1/val_metrics.json

python scripts/export_text_errors.py --data data/text_moderation/sample/test.csv
python scripts/smoke_test_text_baseline.py
python -m pytest -p no:cacheprovider
```

可用 `--experiment` 指定已保存模型目录。训练器只在 train fit TF-IDF 和 GBDT，val 用于
指标/阈值分析，test 不用于参数选择。batch 只进行一次 transform 和一次 predict_proba。
保持 float32 sparse，不执行 `.toarray()`；训练摘要记录 sparse 实际字节数和 dense 估计。
GBDT 在高维稀疏文本上仍可能训练较慢，`max_features` 应根据规模调整。

实验目录 `artifacts/baseline/{experiment_name}/` 保存：

```text
tfidf.joblib / gbdt.joblib / sklearn_version.txt
config.yaml / metrics.json / confusion_matrix.json
threshold_metrics.csv / threshold_summary.json
error_cases.jsonl / training_summary.json / feature_importance.json
```

指标包含 Accuracy、sensitive Precision/Recall/F1、per-class 指标、ROC-AUC 和 average precision
（作为 PR 曲线摘要，字段 `pr_auc_average_precision`）。单类别时 ROC-AUC 为 null。
重点分析 sensitive Recall、F1、PR 指标和 False Negative，而非仅 Accuracy。
阈值分析覆盖 0.1～0.9、步长 0.05，同时给出 best F1 和 recall 目标下的 precision。
probability 是 GBDT 输出，不宣称经过校准。joblib 只可加载可信本地文件，并要求 sklearn
版本与保存时一致。

```python
from visionguard.baseline import TextModerationBaseline

classifier = TextModerationBaseline.load("artifacts/baseline/char_2_4_gbdt_sample_v1")
prediction = classifier.predict(ocr_result.full_text)
prediction_with_source = classifier.predict_ocr(ocr_result)
```

这里只消费 OCR Schema，不初始化 OCR、不使用 OCR confidence，也不建立多模态 Pipeline。

## VLM Adapter（Phase 6）

本模块只审核图片和可选的已保存 Detection/OCR/Baseline 上下文，不自动执行上游模型。
上层依赖 `VLMProvider.analyze(image, context, policy)`；工厂隔离 local/mock 选择。
Local backend 当前支持 Qwen3-VL 架构，默认 `Qwen/Qwen3-VL-2B-Instruct`；更换模型架构
需新增 backend adapter，不能承诺任意 HuggingFace VLM 都兼容同一 processor。

配置 `configs/vlm.yaml` 管理模型、device、dtype、图片/上下文限额、token 上限、deadline、
重试上限、warmup 和 Prompt 版本；`configs/moderation_policy.yaml` 定义允许类别和风险等级。
模型/processor 在 Provider 构造时加载一次。CUDA auto 使用 BF16/FP16，CPU auto 使用 FP32；
OOM 明确报错，不自动重试或静默改为低风险。权重缓存位于 artifacts，首次需联网下载。

```bash
python -m pip install -e ".[dev]"
python scripts/infer_vlm.py --image data/examples/test.jpg --config configs/vlm.yaml --policy configs/moderation_policy.yaml
python scripts/infer_vlm.py --image data/examples/test.jpg --mock
python scripts/infer_vlm.py --image data/examples/test.jpg --detection-json artifacts/detection.json --ocr-json artifacts/ocr.json --baseline-json artifacts/baseline.json
python scripts/create_vlm_eval_samples.py
python scripts/smoke_test_vlm.py --text-image data/vlm_eval/text.png
python scripts/smoke_test_vlm.py --text-image data/vlm_eval/text.png --mock
python scripts/evaluate_vlm.py --manifest data/vlm_eval/manifest.jsonl --mock
python scripts/evaluate_vlm.py --manifest data/vlm_eval/manifest.jsonl
python -m pytest tests/test_vlm.py -p no:cacheprovider
```

VLM evaluation JSONL：`{"image":"safe.png","risk_level":"low","categories":[]}`，图片路径
相对 manifest。更换 experiment_name 后重跑，避免覆盖历史实验。合成低风险样本只能测试
运行和输出可靠性；生成脚本另含一个自构造文字风险样本，但三张样本仍不足以验证真实
类别召回能力。仅有空类别时指标为 0，而非“完美分类”。

```python
from visionguard.vlm import build_context, create_provider, load_vlm_config
from visionguard.moderation.policy import load_policy

provider = create_provider(load_vlm_config("configs/vlm.yaml"))
context = build_context(detection_result, ocr_result, baseline_prediction)
result = provider.analyze(image, context, load_policy("configs/moderation_policy.yaml"))
```

新版 `moderation.schemas.ModerationResult` 是旧统一契约的扩展子类，旧 Phase 1～5 Schema
保持不变；新版输出 categories(name/score)、evidence(type/description/bbox/text)、非空 reason、
requires_manual_review、confidence_score、metadata。高风险必须有证据，类别需经 Policy 校验。
旧 confidence 属性映射为 confidence_score，不在新版 JSON 输出重复。Phase 7 需要显式采用
新版结果类型，而不能假设旧 PipelineResult 序列化会保留子类新增字段。需要旧格式时使用
`result.to_legacy()` 显式转换 categories/evidence；不会保留新 metadata，不能冒充无损转换。

Parser 支持纯 JSON、fenced JSON 和单对象前后少量解释；拒绝多个对象、非法字段和类别。
唯一额外结构转换是四个数的 bbox 数组映射为 x1/y1/x2/y2 对象，保留坐标及结论，并记录
bbox_format_normalized；越界证据框 clamp，完全在图外的框移除，记录 adjusted_evidence_bbox_count。
结构化成功率指经这类确定性格式转换及验证后被接受，不代表原始输出总能严格匹配 Schema。
Malformed JSON 不用 eval 或猜测补值，通过可配置格式重试修复，保持审核结论。
只有明确标记 retryable 的临时异常允许 inference retry，不按 risk level 重试。
彻底失败抛异常，不 fail-open。同步 generation 在 token 间检查 deadline；不能硬中断某一次
阻塞 GPU kernel，因此 timeout 是尽力停止，不是硬实时隔离。初始化时间不计入推理耗时。

Prompt 文件 `prompts/vlm/*_v1.txt` 为固定版本，后续修改新增 v2，不覆盖 v1。OCR 及图片文字
被明确标记为非可信数据，XML 特殊字符转义防止闭合标签逃逸，但这不是完整安全保证。
模型生成没有 JSON constrained decoding；可靠性来自提取、Pydantic/Policy 校验及重试。
confidence_score/category score 是模型自报参考分数，非经过校准的真实概率；bbox 为模型估计，
并不保证达到检测定位精度。图片 resize 保持比例，Prompt 明确要求原图坐标，不确定时省略 bbox。

输出 metadata 包含 provider/model/prompt_version、token 数（local）、retry_count、截断标志和
image_prepare/prompt_build/inference/parse/total_ms。原始响应仅内部格式修复使用，默认不落盘。
`artifacts/vlm/{experiment_name}/` 保存 config.yaml、policy.yaml、prompt_snapshot.txt、metrics.json、
predictions.jsonl、errors.jsonl、summary.json。首次有效率、重试恢复率、最终失败率均以 total
为分母；结构化成功率=(首次有效+重试恢复)/total；invalid output 只计最终解析失败，与模型
运行错误分开；category 指标为 micro，失败样本计漏检，risk accuracy 以全部样本为分母。
Manual Review Rate 只在有效结果上统计；Latency 包含尝试与失败、排除模型加载。

不包含最终 Pipeline、级联推理、融合、API 或 Benchmark。

本机 HuggingFace 传输不稳定时使用 Qwen 官方 ModelScope 同款权重，并在
`configs/local_vlm.yaml`（Git 忽略的本地覆盖）设置 `model_name_or_path` 为下载目录：

```bash
python scripts/smoke_test_vlm.py --config configs/local_vlm.yaml --text-image data/vlm_eval/text.png
python scripts/evaluate_vlm.py --config configs/local_vlm.yaml --manifest data/vlm_eval/manifest.jsonl
```

默认配置不绑定本机目录；也可用 model_revision 固定 HuggingFace commit，以提高可复现性。

## Multimodal Review Pipeline（Phase 7）

Phase 7 使用固定的同步完整调用顺序：图像标准化后依次执行 YOLO、OCR、OCR 文本
Baseline、Phase 6 `build_context()` 与 VLM，最后把 VLM 的核心结论和所有中间结果写入
`ReviewResult`。Pipeline 只接受已经初始化的依赖；模型加载集中在 `pipeline.runner`，因此
同一次 CLI / 服务进程只加载一次模型。Detection、OCR、Baseline 与 VLM 彼此不直接依赖。

本阶段不进行置信度路由或 Risk Fusion。Detection 与 Baseline 只是 VLM 上下文证据；VLM
失败时 `final.risk_level` 为 `null`、`review_status=partial` 且强制人工复核，绝不会默认判为
low。默认 `fail_fast=false`，单模块失败会记录错误类型、精简消息和耗时，其余可运行模块继续。
图像加载失败是 fatal；artifact 保存失败不会推翻已经完成的审核结果。

`configs/pipeline.yaml` 控制四个模块开关、artifact、可视化、输入副本、fail-fast、Pipeline
版本、OCR 输入 Baseline 的字符上限与 trace。四个模块默认全部开启；模块开关仅用于测试和
消融实验，不是 Phase 8 的动态路由策略。

```bash
python scripts/run_pipeline.py \
  --image data/vlm_eval/risky.png \
  --pipeline-config configs/pipeline.yaml \
  --detector-config configs/detector.yaml \
  --ocr-config configs/ocr.yaml \
  --baseline-config configs/baseline_text.yaml \
  --vlm-config configs/local_vlm.yaml \
  --policy configs/moderation_policy.yaml
```

真实 smoke test 会复用同一组已初始化模型；传入的样本应覆盖普通图片、文字图片、风险文字、
有检测结果的图片与无文字图片：

```bash
python scripts/smoke_test_pipeline.py \
  --images data/vlm_eval/safe.png data/ocr_smoke/chinese.png \
           data/vlm_eval/risky.png data/visionguard_smoke/images/train/train_00.jpg \
  --detector-config configs/detector.yaml \
  --vlm-config configs/local_vlm.yaml
```

Evaluation manifest 每行包含相对图片路径、risk_level 和 categories。下面的少量合成样本仅
用于工程链路验收，不能作为真实出版内容审核准确率结论：

```json
{"image":"safe.png","risk_level":"low","categories":[]}
```

```bash
python scripts/evaluate_pipeline.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --output artifacts/pipeline/evaluation_v1 \
  --detector-config configs/detector.yaml \
  --vlm-config configs/local_vlm.yaml
```

每次运行生成 UUID4 `run_id`，日志、JSON 和目录都使用该 ID。默认不复制输入原图，只保存
源路径、标准化像素 SHA-256 与可视化；`save_input_copy=true` 时才额外保存输入副本。

```text
artifacts/pipeline/{run_id}/
├── input_metadata.json
├── detection.json / ocr.json / baseline.json / vlm.json
├── review_result.json / timing.json
├── error.json                  # 有模块失败时
└── visualizations/
    ├── detection.jpg
    └── ocr.jpg
```

`routing_signals` 保留 detection confidence/count、OCR confidence/block count、Baseline
probability、VLM confidence/manual-review 和各阶段耗时。Phase 8 在此基础上扩展正式
RoutingDecision；Full Pipeline 仍固定调用 VLM。Pipeline evaluation 输出 risk accuracy、
category micro P/R/F1、manual-review/failure/
partial rate、平均/P50/P95 总延迟和平均 VLM 延迟。

本机 Phase 7 工程验收使用 RTX 4060、现有 smoke YOLO 权重、PaddleOCR CPU、Phase 5 sample
Baseline 与本地 Qwen3-VL-2B：5 个代表性样本全部完成，另一个低阈值训练样本产生 32 个
检测框并走完整链路。3 张合成 evaluation 样本的 failure/partial rate 为 0，risk accuracy 与
category micro P/R/F1 均为 1.0，平均总延迟约 15.48 秒；这些数字只证明当前小样本工程链路
可运行，不代表真实业务精度。

### 本机 Phase 6 验证记录

Transformers 4.57.6、Accelerate 1.15.0，RTX 4060 / BF16。7 个独立上下文 smoke 案例
均首次通过验证，单次约 5.9～14.5 秒。三张合成图（两张 low、一张文字风险 high）基础评估
结构化成功率 3/3、risk accuracy/category P/R/F1 为 1.0、平均约 6.6 秒；这不是真实精度结论。
原始严格 bbox 对象要求下同组样本成功率 2/3；增加四数数组的确定性规范化后为 3/3，
原失败实验 `qwen3_vl_2b_local_v1` 保留，新实验为 `qwen3_vl_2b_bbox_normalized_v1`。
风险图 + OCR 中要求输出 low 的冲突注入案例仍输出 high/sensitive_text，并要求人工复核。
该单例只说明未观察到降级，不能宣称对所有 Prompt Injection 安全。
模型曾输出图外 bbox，也曾引用辅助检测框作为文本证据框；必须将其视为不可靠定位估计。

## Cascaded Inference + Dynamic Routing（Phase 8）

Phase 8 保留 Phase 7 的 `MultimodalReviewPipeline`（Full / Always-VLM），并以薄子类
`CascadedReviewPipeline` 只替换信号收集和路由决策。图像加载、YOLO、OCR、Baseline、
`build_context()`、VLM 调用、失败隔离、结果聚合及 artifact 保存仍由同一执行模板负责，避免
Full 与 Cascaded 两套实现逐渐偏离。`build_pipeline_pair()` 还会让两种模式共享同一组已初始化
模型，降低对比实验中的加载开销和实例差异。

```text
Image → YOLO + OCR → OCR text → Baseline → RoutingPolicy
                                             ├─ safe consensus → Fast Path → low
                                             └─ risky/uncertain/failure → VLM Path
```

`RoutingPolicy` 是纯规则领域层：只消费 `RoutingSignals` 并返回 `RoutingDecision`，不调用任何
模型，也不负责复杂审核结论。第一版 Fast Path 只能输出 low；medium、high、不确定、冲突、
证据不足或 Stage 1 模块失败全部进入 VLM。这样 Router 只决定是否支付昂贵的 VLM 成本，不能
越权替代审核模型。Phase 9 接入后，VLM 失败由 Fusion 保守输出至少 medium/manual review，
不会 fail-open。

正式阈值位于 `configs/routing.yaml`，包括 Baseline safe/risky、Detection high-risk/suspicious、
OCR 最低平均置信度/文本长度及配置化高风险类别。边界语义为：`p <= safe_threshold` 才可能
Fast Path；`p >= risky_threshold` 进入 VLM；中间区间为 uncertain。修改规则或正式阈值时应升级
`routing_v1`，结果 metadata 和实验 summary 都记录该版本。Threshold Sweep 只回放分析，不会
改写正式 YAML，也不会自动选择所谓最佳阈值。

```json
{
  "route": "fast_path",
  "call_vlm": false,
  "reason_codes": ["no_detection", "safe_consensus"],
  "explanation": "Fast-path low risk allowed by conservative safe consensus.",
  "signals": {
    "detection_count": 0,
    "mean_ocr_confidence": 0.94,
    "baseline_probability": 0.04,
    "detector_status": "success",
    "ocr_status": "success",
    "baseline_status": "success"
  },
  "policy_version": "routing_v1"
}
```

Full Pipeline 与 Cascaded 单图命令：

```bash
python scripts/run_pipeline.py \
  --image data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml

python scripts/run_cascaded_pipeline.py \
  --image data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml
```

Mock 单测和真实 smoke test：

```bash
python -m pytest tests/test_routing_policy.py tests/test_cascaded_pipeline.py \
  tests/test_routing_evaluator.py -p no:cacheprovider

python scripts/smoke_test_cascaded.py \
  --images data/vlm_eval/safe.png data/vlm_eval/text.png data/vlm_eval/risky.png \
           data/ocr_smoke/chinese.png data/visionguard_smoke/images/train/train_00.jpg \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml
```

评估、Full/Cascaded 对比和阈值扫描都要求使用新的空输出目录，以免覆盖历史实验：

```bash
python scripts/evaluate_routing.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --output artifacts/routing/cascaded_eval_v1 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml

python scripts/compare_pipeline_modes.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --output artifacts/routing/comparison_v1 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml

python scripts/sweep_routing_thresholds.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --output artifacts/routing/threshold_sweep_v1 \
  --safe-thresholds 0.05 0.10 0.15 0.20 0.30 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml
```

`Unsafe Fast Pass` 定义为 GT 是 medium/high、Router 却选择 fast_path。这是首要安全指标，
会以 count、占全部样本比例和占 need-vlm 样本比例单独输出。Routing Precision/Recall/F1 使用
`low → candidate_skip`、`medium/high → need_vlm` 的工程代理标签；它不等于“该样本客观上一定
需要 VLM”。`potential unnecessary VLM call` 也只是 GT low 且 VLM 仍判 low 的分析候选，
不能证明这次调用绝对没有必要。

```bash
python scripts/analyze_routing_errors.py \
  --predictions artifacts/routing/cascaded_eval_v1/predictions.jsonl \
  --output artifacts/routing/errors_v1
```

错误分析生成 `routing_errors.jsonl`、`summary.json`，并按 `unsafe_fast_pass/`、
`potential_unnecessary_vlm/`、`conflict/`、`module_failure_route/` 分类复制样本。每条记录包含图片、
GT、route、reason codes、signals 和最终结果。每次推理目录额外包含 `routing.json`：

```text
artifacts/routing/
├── cascaded_routing_v1/{run_id}/
│   ├── routing.json
│   ├── review_result.json / timing.json
│   ├── detection.json / ocr.json / baseline.json / vlm.json
│   └── visualizations/
├── comparison_v1/{full,cascaded}/
├── threshold_sweep_v1/
└── errors_v1/
```

本机 Phase 8 工程验收使用 RTX 4060、smoke YOLO、PaddleOCR CPU、sample Baseline 和本地
Qwen3-VL-2B。5 张真实 smoke 输入全部完成，其中 2 张明确安全文本图跳过 VLM，风险文本、
无文字和低 OCR 质量样本进入 VLM。3 张合成 evaluation 样本上，Full → Cascaded 的 VLM
Call Rate 为 100% → 66.7%，Skip Rate 为 0% → 33.3%，平均延迟约 20.13s → 13.05s，
P50 约 22.25s → 9.47s，P95 约 27.36s → 25.95s，Unsafe Fast Pass 为 0，risk accuracy 和
category micro P/R/F1 均为 1.0。阈值扫描链路已验证，但这 3 个样本在 0.05～0.30 间路由结果
相同。以上数字只证明小型合成数据上的工程链路与观测能力，不能代表真实出版审核效果；正式
阈值必须用规模更大、类别覆盖完整且经过人工标注的数据集确定。Phase 8 的 Routing 与 Phase 9
Fusion 保持独立；当前仍是同步单图、规则路由，不包含 ML Router、Batch Benchmark、服务化或
分布式调度。

## Risk Fusion + Multimodal Decision Fusion（Phase 9）

Phase 9 将最终结论从“直接采用 VLM 或 Fast Path low”升级为独立 `RiskFusionEngine`。Routing
只决定是否调用 VLM；Fusion 只消费扁平 `FusionSignals` 并决定最终风险。两者不互相承担对方
职责，Full 与 Cascaded Pipeline 共用同一个无状态 FusionEngine。

```text
Full:      YOLO + OCR + Baseline + VLM → Fusion → FusionDecision
Cascaded: YOLO + OCR + Baseline → Routing
                                  ├─ Fast Path → pre-fusion safety guard
                                  │               ├─ low → final fusion
                                  │               └─ non-low → override → VLM → final fusion
                                  └─ VLM Path → VLM → final fusion
```

正式配置位于 `configs/fusion.yaml`，版本为 `fusion_v1`。Detector severity、Baseline/OCR 阈值、
VLM level score、visual/text/VLM 权重、风险边界、失败/冲突策略和 uncertainty margin 均配置化。
修改正式规则或阈值时应升级 policy version。Pipeline 配置版本升级为 v2，新的默认运行目录为
`artifacts/fusion/full_fusion_v1/` 与 `artifacts/fusion/cascaded_fusion_v1/`，不会覆盖 Phase 8 目录。

第一版 weighted score：

```text
visual_score = max(detection_confidence × class_severity)
text_score   = baseline_probability × mean_ocr_confidence
vlm_score    = configured(low=0.15, medium=0.60, high=0.90)
risk_score   = Σ(normalized_available_weight × available_score)
```

默认权重为 visual=0.25、text=0.20、VLM=0.55。缺少 VLM 时只在 visual/text 上重新归一化，
不会将 VLM 人为当作 0 分。OCR confidence 只决定文本证据可靠性，不直接代表审核风险。
VLM confidence 默认不缩放分数，因为该值未经校准；即使开启，也只做谨慎缩放。
`risk_score` 是工程融合分，不是严格校准概率。

```json
{
  "risk_level": "high",
  "risk_score": 0.71,
  "categories": [
    {"name": "weapon", "score": 0.91, "sources": ["detector", "vlm"]}
  ],
  "requires_manual_review": false,
  "decision_source": "fusion",
  "reason_codes": ["visual_risk", "vlm_risk"],
  "policy_version": "fusion_v1",
  "metadata": {
    "vlm_used": true,
    "routing_policy_version": "routing_v1",
    "fusion_policy_version": "fusion_v1",
    "score_is_calibrated_probability": false
  }
}
```

冲突包括 high visual/VLM low、Baseline high/VLM low、VLM high/其他证据均低，以及高 Baseline
配合低可靠 OCR。冲突不会通过多数投票隐藏，而是保留 provenance 并强制人工复核。`failed`
模块从可用权重中移除，同时保守地至少输出 medium/manual；合法 `skipped` 不视为故障。距离
0.30 或 0.70 决策边界小于 0.05 时增加 `near_decision_boundary` 并要求人工复核。

Fast Path safety guard 示例：Routing 原判 fast_path，但 Stage 1 visual/text 融合为 medium；Pipeline
将路由改为 vlm_path，记录 `original_route=fast_path`、`fusion_safety_guard` 和
`routing_overridden_by_fusion=true`，再调用 VLM。若 VLM 被禁用，则不 Fast Pass，保守进入人工复核。

单图和测试：

```bash
python scripts/run_pipeline.py --image data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml \
  --fusion-config configs/fusion.yaml

python scripts/run_cascaded_pipeline.py --image data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml \
  --fusion-config configs/fusion.yaml

python -m pytest tests/test_fusion_engine.py tests/test_fusion_conflicts.py \
  tests/test_fusion_missing_modules.py tests/test_fusion_evaluator.py -p no:cacheprovider
```

Live Fusion Evaluation 只运行一次昂贵模型，并保存可重放 `records.jsonl`：

```bash
python scripts/evaluate_fusion.py --mode cascaded \
  --manifest data/vlm_eval/manifest.jsonl \
  --output artifacts/fusion/evaluation_v1 \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml
```

下面的 strategy、ablation 和 sweep 全部消费同一份 records，不重复运行 YOLO/OCR/VLM：

```bash
python scripts/compare_fusion_strategies.py \
  --records artifacts/fusion/evaluation_v1/records.jsonl \
  --output artifacts/fusion/strategy_compare_v1

python scripts/run_fusion_ablation.py \
  --records artifacts/fusion/evaluation_v1/records.jsonl \
  --output artifacts/fusion/ablation_v1

python scripts/sweep_fusion.py \
  --records artifacts/fusion/evaluation_v1/records.jsonl \
  --output artifacts/fusion/sweep_v1 \
  --low-max-values 0.25 0.30 0.35 \
  --weight-sets 0.25,0.20,0.55 0.30,0.25,0.45
```

历史 Phase 7/8/9 artifact replay 和错误分析：

```bash
python scripts/replay_fusion.py \
  --artifacts artifacts/routing/cascaded_routing_v1 \
  --output artifacts/fusion/replay_v1.jsonl

python scripts/analyze_fusion_errors.py \
  --records artifacts/fusion/evaluation_v1/records.jsonl \
  --output artifacts/fusion/errors_v1
```

Error Analysis 分类保存 false_low、false_high、evidence_conflict、near_boundary、module_failure 和
routing_override；其中 GT medium/high 但 Fusion low 会单独统计为 `unsafe_fused_low`。每个新运行
除 routing.json 外还保存 fusion.json，包含扁平 signals、visual/text/VLM scores、归一化权重、
最终分数、原因和 provenance。

本机 Phase 9 工程验证使用 RTX 4060、smoke YOLO、PaddleOCR CPU、sample Baseline 和本地
Qwen3-VL-2B。5 张真实 smoke 输入全部完成；3 张合成 evaluation 样本的 Risk Accuracy 与
Category micro F1 为 1.0，Manual Review Rate 33.3%，Conflict Rate 0%，Near-boundary Rate
33.3%，Routing Override Rate 0%，Unsafe Fused Low 为 0。离线策略对比中 VLM-only Risk
Accuracy 为 66.7%，hard-rule/weighted 为 100%；这只表明当前小样本上文本 Baseline 提供了
额外工程信号，不能证明 Fusion 在真实数据上必然优于 VLM。五组 ablation、六组阈值/权重组合、
16 个历史 artifact replay 和 Error Analysis 链路均已运行。正式权重、阈值和 safety override
必须在规模更大、类别覆盖完整、人工标注且具有真实冲突/失败案例的数据集上重新评估。当前不包含
ML/Neural Fusion、自动阈值选择、FastAPI、异步队列或分布式调度。

## Batch Inference Benchmark + Performance Profiling（Phase 10）

Phase 10 提供独立于业务 Pipeline 的可复现性能测量层。正式配置位于
`configs/benchmark.yaml`；`configs/benchmark_smoke.yaml` 只用于 batch 1/2 快速验证。
所有实验写入新的独立目录，如果目标目录已存在会直接报错，不覆盖历史数据。

批量模式严格区分：

| 模块 | Batch mode | 说明 |
|---|---|---|
| YOLO | `true_batch` | 多张 BGR ndarray 一次进入 Ultralytics |
| Baseline | `true_batch` | 一次 TF-IDF transform 和一次 `predict_proba` |
| PaddleOCR | `sequential` | 当前稳定 Provider API 按单图解析 |
| Qwen3-VL | `sequential` | 保持独立结构化解析与单样本错误隔离 |
| Pipeline | `mixed` | YOLO/文本批量，OCR 顺序，Routing 后选择性调用 VLM |

CUDA kernel 是异步执行的。Benchmark 会按配置在计时前后调用
`torch.cuda.synchronize()`，并在测量前重置 peak memory；该同步只存在于 Benchmark 层，不会改变
生产 Pipeline。显存字段分别表示当前 allocated、PyTorch reserved 和区间 peak allocated，它们不能
互相替代。模型构造和模型内部 warmup 计入 `startup_time_ms`；首个请求单独记录为
`cold_inference_ms`，配置 warmup 不进入 steady-state percentile。

Pipeline mixed batch 数据流：

```text
Batch images
  → YOLO true batch
  → OCR sequential
  → Baseline true batch（仅非空 OCR 文本）
  → Routing + pre-fusion safety guard
  → selected VLM subset（当前 sequential）
  → Fusion per sample
  → ordered ReviewResult list
```

`data/benchmark/manifest.jsonl` 是 20 条工作负载记录，覆盖 safe/risky text、OCR-heavy、visual、
no-text、Fast/VLM path；其中包含对已有 smoke 图片的重复引用，用于工程性能测量，不是正式审核
准确率数据集。可通过固定 seed 随机顺序，避免固定输入顺序造成缓存偏差。

单模块 Benchmark：

```bash
python scripts/benchmark_modules.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark.yaml --batch-size 4 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/phase10_modules_v1
```

Full / Cascaded Pipeline：

```bash
python scripts/benchmark_pipeline.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark.yaml --pipeline-mode full --batch-size 4 \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/phase10_full_v1

python scripts/benchmark_pipeline.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark.yaml --pipeline-mode cascaded --batch-size 4 \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/phase10_cascaded_v1
```

Batch size sweep 和公平比较：

```bash
python scripts/benchmark_batch_sizes.py \
  --manifest data/benchmark/manifest.jsonl --config configs/benchmark.yaml \
  --pipeline-mode cascaded \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/phase10_batch_sweep_v1

python scripts/compare_pipeline_performance.py \
  --manifest data/benchmark/manifest.jsonl --config configs/benchmark.yaml --batch-size 4 \
  --detector-config configs/local_detector.yaml --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/phase10_full_vs_cascaded_v1
```

Full/Cascaded 对比共享相同模型实例、样本、batch size、seed、warmup 和硬件，并关闭每请求 Pipeline
artifact 写入。输出包括 `records.jsonl`、`summary.json`、`summary.csv` 和
`performance_report.md`。报告可从已有 summary 重新生成：

如需单独测量 artifact I/O，将 benchmark 配置中的 `save_pipeline_artifacts` 改为 `true`。该模式会
明确标记为 `sequential`，并把请求产物写入独立的 `*_request_artifacts` 目录；不要将关闭 artifact
得到的差异描述为模型推理优化。

```bash
python scripts/generate_performance_report.py \
  --input artifacts/benchmarks/phase10_full_vs_cascaded_v1 \
  --output artifacts/benchmarks/phase10_full_vs_cascaded_v1_report.md
```

每条记录明确保存 batch latency、per-sample latency、images/s、VLM 调用数/调用率、人工复核数、
失败数、模块耗时与显存。汇总包含 Mean、Median、Std、Min、Max、P50/P90/P95/P99、Fast/VLM
Path 平均延迟和模块耗时占比。CUDA OOM 会保存为 `status=oom`、清理 cache 并继续 sweep；其他异常
不会被静默吞掉。

环境快照只记录 Python、OS、PyTorch/CUDA、GPU 型号/显存以及关键库版本，不记录用户名、私有路径、
token。性能结论只适用于记录的单消费级 GPU、软件版本和工程数据集，不能泛化为所有部署环境。
当前未实现真正的 OCR/VLM batch、异步请求队列、跨请求动态 batching、TensorRT、Triton、分布式或
多 GPU 推理，也未进入 FastAPI 阶段。

本机 RTX 4060 Laptop GPU 的一次 Phase 10 smoke（每组仅 1 次 measured run）结果如下：

| Mode | Batch | Mean/P50/P95/P99 ms | Throughput | VLM rate | Peak GPU MB |
|---|---:|---:|---:|---:|---:|
| Cascaded | 1 | 7849.80 | 0.127 images/s | 100% | 6309.1 |
| Cascaded | 2 | 17398.41 | 0.115 images/s | 100% | 4588.7 |
| Full | 2 | 16218.14 | 0.123 images/s | 100% | 4593.4 |
| Cascaded comparison | 2 | 16383.42 | 0.122 images/s | 100% | 4593.4 |

该 smoke 的 batch 2 样本全部被路由至 VLM，因此 Cascaded 没有降低 VLM Call Rate，平均延迟相对
Full 反而有约 1.02% 的正常测量波动，不能宣称性能提升。VLM 占 Full 约 91.21%、Cascaded 约
90.57% 的模块时间，是当前明确瓶颈。由于每组只有一次正式测量，P50/P95/P99 数值相同；正式结论
必须使用 `configs/benchmark.yaml` 的多次测量和覆盖 Fast Path/VLM Path 的更大真实工作负载。

## FastAPI 推理服务（Phase 12）

Phase 12 将现有同步 Pipeline 封装为单进程、单 GPU 推理服务。模型在 FastAPI lifespan
启动阶段只初始化一次，Full 与 Cascaded Pipeline 共享同一组 Detector、OCR、Baseline、VLM、
Policy 和 Fusion 实例；请求只负责图片校验、模式选择、排队、推理及稳定 API Schema 转换。

安装与配置：

```bash
pip install -e .
python scripts/run_api.py --config configs/api.yaml
```

真实模型 smoke 或性能检查不要开启 reload，也不要使用多个 Uvicorn worker。每个 worker 都会
独立加载模型并重复占用显存。默认 `max_concurrent_inference: 1`，整个同步 Pipeline 在
`asyncio.Semaphore` 内通过 worker thread 执行，避免阻塞 HTTP event loop，也避免 Qwen3-VL、
PaddleOCR 和 YOLO 在未验证线程安全与显存边界前并行执行。主要配置位于
`configs/api.yaml`，包括上传大小、图片维度、超时、并发、默认 Pipeline 模式、artifact 和 warmup。

健康检查与元数据：

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/v1/meta
```

`live` 只验证进程可响应；`ready` 只读取启动状态，不运行模型；`meta` 返回服务、Pipeline、策略、
Prompt 版本和经过脱敏的模型标识，不返回本地绝对路径。OpenAPI 位于 `/docs` 和
`/openapi.json`，可通过 `docs_enabled` 关闭。

Review API 默认使用 Cascaded Pipeline，也可显式选择 Full：

```bash
curl -X POST \
  "http://127.0.0.1:8000/v1/review?pipeline_mode=cascaded&include_details=false" \
  -H "accept: application/json" \
  -F "file=@data/example.png"

curl -X POST \
  "http://127.0.0.1:8000/v1/review?pipeline_mode=full&save_artifacts=false" \
  -F "file=@data/example.png"
```

Python 客户端示例：

```python
import requests

with open("data/example.png", "rb") as image:
    response = requests.post(
        "http://127.0.0.1:8000/v1/review",
        params={"pipeline_mode": "cascaded", "include_details": False},
        files={"file": ("example.png", image, "image/png")},
        timeout=120,
    )
response.raise_for_status()
print(response.json())
```

成功响应使用固定 `api_version: v1`，包含独立的 `request_id` 与 Pipeline `run_id`、最终风险结论、
Routing 摘要、模块状态、版本信息及以下时间：

```json
{
  "request_id": "http-request-id",
  "run_id": "pipeline-run-id",
  "status": "completed",
  "result": {
    "risk_level": "low",
    "risk_score": 0.12,
    "categories": [],
    "requires_manual_review": false,
    "reason": "...",
    "decision_source": "fusion"
  },
  "timing": {
    "request_total_ms": 8100.0,
    "queue_wait_ms": 120.0,
    "inference_ms": 7900.0,
    "response_serialization_ms": 1.0,
    "pipeline_total_ms": 7850.0,
    "detector_ms": 40.0,
    "ocr_ms": 300.0,
    "baseline_ms": 2.0,
    "routing_ms": 1.0,
    "vlm_ms": 7100.0,
    "fusion_ms": 1.0
  }
}
```

`queue_wait_ms` 是等待推理信号量的时间，不属于模型推理时间。`include_details=true` 仅增加检测框、
OCR 计数/长度/平均置信度、Baseline/VLM 摘要和 Fusion provenance；不会返回完整 OCR 文本、原始
VLM 输出、Prompt 或秘密配置。上传采用有界分块读取并在内存中解码，不接受服务器文件路径，也不
创建临时图片。

已知错误统一返回：

```json
{
  "error": {
    "code": "INVALID_IMAGE",
    "message": "Uploaded file is not a valid image.",
    "request_id": "...",
    "run_id": null,
    "details": null
  }
}
```

HTTP 映射为：无效输入 400、上传过大 413、不支持 MIME 415、请求 Schema 422、未就绪 503、
服务层超时 504、Pipeline/未知异常 500。Pipeline 返回 partial 仍是 HTTP 200，并通过
`requires_manual_review` 表达降级结果。服务超时不是 GPU hard cancellation：已经进入 worker
thread 的推理可能继续运行，并继续持有 semaphore，直到同步 Pipeline 自然结束。关闭服务时会先
停止接收新推理并在 grace period 内等待活动任务；只有任务结束后才释放模型引用和清理 CUDA cache。

默认 API artifact 复用 `artifacts/pipeline/{run_id}`，响应只返回 `artifact_id=run_id`，不暴露
服务器路径。Pipeline 默认 `save_input_copy=false`，因此不会因 API 上传自动永久保存原图。

Mock API 测试与真实服务 smoke：

```bash
pytest tests/test_api_*.py

python scripts/smoke_test_api.py \
  --safe-image data/examples/safe.png \
  --risky-image data/examples/risky.png
```

当前服务不包含认证、CORS、数据库、Redis/Celery、动态 batching、多 worker 模型共享、分布式或
多 GPU 调度。正式公网部署前仍需在服务边界外增加 TLS、认证、流量限制及受控来源策略。
