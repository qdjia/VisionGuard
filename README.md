# VisionGuard

基于视觉语言模型的多模态出版内容智能审校系统。

本项目面向 AI / Computer Vision 算法作品集，采用 YOLO、OCR、规则引擎与 VLM
组成多阶段级联推理流水线。当前完成到 **Phase 4：OCR 模块**。

## 安装与测试

```bash
python -m pip install -e ".[dev]"
pytest
```

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

当前已实现配置与 Schema、YOLO26 单图推理、YOLO 数据集/训练/评估，以及 PaddleOCR
全图/ROI 推理和 CER 基础评估。尚未实现文本 Baseline、VLM、规则引擎、最终多模态
Pipeline、级联推理、正式 Batch Benchmark、综合 Error Analysis 或 FastAPI。
