# VisionGuard

基于视觉语言模型的多模态出版内容智能审校系统。

本项目面向 AI / Computer Vision 算法作品集，采用 YOLO、OCR、规则引擎与 VLM
组成多阶段级联推理流水线。当前开发到 **Phase 7：Multimodal Review Pipeline**。

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
全图/ROI 推理和 CER 基础评估、传统文本 Baseline、独立 VLM Adapter 和同步多模态 Review
Pipeline。尚未实现规则引擎、级联推理、正式 Batch Benchmark、综合 Error Analysis 或 FastAPI。

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
probability、VLM confidence/manual-review 和各阶段耗时，供 Phase 8 使用；当前没有 routing
policy。Pipeline evaluation 输出 risk accuracy、category micro P/R/F1、manual-review/failure/
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
