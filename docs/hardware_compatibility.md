# Hardware Compatibility Matrix

“已验证”不等于“最低要求”。最低 GPU、VRAM、内存和 CPU 要求只有在多档硬件重复测试后才能确定。

| 日期 | 系统 / 硬件 | Driver / CUDA | Core | Advanced AI | 结论 |
|---|---|---|---|---|---|
| 2026-09-14 | Windows，NVIDIA GeForce RTX 4060 Laptop，8 GiB VRAM；CPU/RAM 未记录 | Driver 580.97；驱动报告 CUDA 13.0 | 通过开发机 smoke | Qwen3-VL-2B 离线推理、lazy load、restart、crash isolation 通过 | Validated configuration，仅代表开发验证 |

Core 和 Advanced AI 的最低硬件要求尚未充分刻画。RTX 4060 Laptop 8 GiB 只能写为 `Validated On`。Clean Windows VM / Sandbox 结果尚未记录，不得标为通过。
