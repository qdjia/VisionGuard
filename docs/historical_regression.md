# 历史回归验收记录

候选版本：`1.0.0-rc.1`<br>
审计更新：2026-10-04<br>
当前结论：**BLOCKED**。`routing_v3` 保持零错误 fast path，VLM/policy v2 已将确认回归从 15 个降至 0；仍有 4 个潜在回归需要人工裁定，并且最终矩阵尚未在干净机器复跑。Legacy Full Runtime 继续仅作参考。

## 真实图片数据集

项目使用 27 张经人工核验、许可可追溯的 Wikimedia Commons 真实图片。锁定清单位于 `data/regression/real_image_manifest.jsonl`，记录来源页面、修订号、许可证、作者、Commons SHA-1、本地 SHA-256、尺寸和人工 ground truth。图片二进制只保存在验收目录，不进入 Git。

数据集覆盖 safe publishing、multilingual text、QR code、weapon、violence、blood、prohibited symbol 和 watermark。27/27 标注已核验，所有文件哈希验证通过。

## 2026-10-03 `routing_v3` 修复验证

根因是旧安全共识仅依赖 OCR 字符长度、OCR 置信度和 Baseline 低风险结果。当检测器漏检视觉风险时，图片中的少量偶然文字也可能触发 fast path。重复符号还可能被 OCR 识别成覆盖面积较大的“文本”，因此只增加文本面积阈值仍不充分。

`routing_v3` 将以下条件同时纳入可配置的安全共识：

- OCR 文本面积占比至少 `0.12`；
- OCR 文本块至少 `4` 个；
- OCR 总字符数至少 `32`；
- 原有 OCR 置信度、Baseline 安全阈值、无高风险检测与无证据冲突条件继续生效。

使用重建后的打包 Core Runtime 与 Gate 3 托管本地 GPU VLM，在开发验收机回放未改动的 27 张锁定图片：

- Equivalent：11
- Expected Difference：1
- Potential Regression：0
- Confirmed Regression：15
- 错误 fast path：0（基线为 7）
- VLM 调用：25/27，调用率 `92.5926%`
- 总耗时：634.281 秒

原先 7 个错误 fast path 已全部消除。`real-024` 的重复禁用符号此前会被 OCR 误判为足量文本，现在因 `SPARSE_TEXT_CONTEXT` 进入 VLM，并得到与标注一致的审核结果。两张正文占主导的安全出版页面仍保留 fast path。

剩余 15 个确认回归均已进入 VLM 路径，分布为：QR code 3、weapon 4、violence 3、blood 2、visual sensitive region 1、watermark 2。它们属于下一阶段的 VLM/融合决策修复范围，本次没有修改 ground truth、降低 Gate 或隐藏失败。

完整、无私人路径的结构化结果保存在 `release-evidence/historical-real-image-regression.json`。

## 2026-10-04 VLM/policy v2 修复验证

确认回归的主要根因包括：审核策略缺少部分视觉类别；VLM v1 提示没有稳定约束类别映射；小模型偶尔返回可恢复的类别字符串、错误 evidence type 或不一致的风险/人工复核组合；远程 VLM 允许 210 秒，但 API 外层原先会在 90 秒先行中断。

本轮新增完整视觉类别策略、版本化 v2 prompt、受策略边界约束的结构标准化、保守风险一致性校验，并把 API 请求预算调整为 240 秒，使其严格大于 VLM 的 210 秒预算。没有修改锁定图片、ground truth、路由 Gate 或确认回归判定规则。

使用最终 v2 prompt、重建后的打包 Core Runtime、Gate 3 托管本地 GPU VLM，在同一开发验收机完整回放 27 张锁定图片：

- Equivalent：19
- Expected Difference：4
- Potential Regression：4
- Confirmed Regression：0（修复前为 15）
- 错误 fast path：0
- VLM 调用：25/27，调用率 `92.5926%`
- 总耗时：1900.361 秒

4 个潜在回归为 `real-007`、`real-015`、`real-021`、`real-024`。它们均输出 `medium` 并要求人工复核，因此没有不安全放行；问题集中在 2B VLM 的细粒度类别槽与理由不一致，或标注目标无法从可见内容明确确认。为避免把验收答案硬编码进程序，这些案例继续保留为未决项。

## 证据清单

| 历史来源 | 当前证据 | 状态 |
|---|---|---|
| Phase 6 VLM | VLM schema/provider/prompt-injection tests、`data/vlm_eval` 与 27 张锁定真实图片 | 开发机 0 confirmed，4 potential 待裁定 |
| Phase 7 pipeline | Pipeline 单元/集成测试 | 源码测试通过 |
| Phase 8 routing | Routing policy/evaluator tests | 源码测试通过，真实图片错误 fast path 为 0 |
| Phase 9 fusion | 边界、冲突、模块缺失测试 | 源码测试通过；真实图片无确认回归、仍有 4 个潜在项 |
| Phase 11 hard cases | `data/hard_cases/manifest.jsonl` | 2 条记录，仅 1 条可用于在线回归 |
| Phase 12 API | API tests 与 packaged Core smoke | 开发机通过 |
| Phase 17 deployment | Core model/runtime manifests 与 smoke evidence | 开发机通过 |
| Phase 18 component integration | Packaged Core + VLM smoke 与崩溃隔离 | 开发机曾通过 |

## 固定行为合同

`data/regression/contract_manifest.jsonl` 固定 16 个行为合同，覆盖 safe、risky、no text、OCR low confidence、baseline ambiguous、detector high risk、evidence conflict、prompt injection、fast path、VLM route、no VLM、VLM failure、partial result、fusion boundary、routing boundary 和 structured-output recovery。

这 16 项是源码级行为合同，不能替代真实图片模型质量集，也不能把 clean-machine replay 标为 PASS。

## 2026-09-25 hard-case 诊断

现有 manifest 曾使用真实 YOLO、PaddleOCR、Baseline 与本地 Qwen 在开发机执行：总计 2 条，1 条不可评估，1 条带诊断标志。可评估风险样本仍正确分类为 `high`，进入 VLM 并要求人工复核。Fusion 分数为 `0.700001`，仅比高风险边界高 `0.000001`，因此标记为 **DIAGNOSTIC_ONLY**，不是 `CONFIRMED_REGRESSION`。

原始执行产物含开发机路径，按设计由 Git 忽略；仓库仅保留无私人绝对路径的摘要。

## 后续阻塞项

1. 人工裁定 `real-007`、`real-015`、`real-021`、`real-024` 四个潜在回归，不修改 ground truth 来迎合模型输出。
2. 对确定为模型缺陷的案例评估更强或量化后的 VLM，不在 parser 中硬编码样本答案。
3. 开发机达到 0 confirmed / 0 unresolved potential 后，在干净验收机重复回放。

在锁定真实图片矩阵达到零确认回归、零未决潜在回归并通过干净机器验证前，Historical Regression 保持 `BLOCKED`，Legacy source 不能标记为 Safe To Retire。
