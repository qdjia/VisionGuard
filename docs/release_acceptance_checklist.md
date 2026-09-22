# VisionGuard Windows Release Acceptance Checklist

候选版本：`________________`　测试日期：`________________`　测试人：`________________`

本清单必须在没有 Python、Node、Rust、源码仓库和开发虚拟环境的 Windows Sandbox 或干净 VM 中执行。未实际执行的项目不得勾选。

## 安装与首次启动

- [ ] 验证安装器 SHA-256 与 `SHA256SUMS.txt` 一致
- [ ] 断网启动安装器，安装成功
- [ ] 安装过程不要求管理员权限
- [ ] Start Menu 出现 VisionGuard
- [ ] 勾选后桌面出现 VisionGuard 快捷方式
- [ ] 快捷方式打开的是 VisionGuard，不是 Runtime 控制台
- [ ] 首次启动显示真实 Runtime/Model 状态
- [ ] 缺少模型时显示 Model Setup，不显示 Python traceback
- [ ] 缺少 Runtime 时显示 Runtime Setup，不显示命令行或 traceback
- [ ] Runtime ZIP/目录导入成功，篡改文件触发 `RUNTIME_HASH_MISMATCH`
- [ ] 模型 ZIP 导入成功
- [ ] 已解压模型目录导入成功
- [ ] 篡改模型触发 `MODEL_HASH_MISMATCH`
- [ ] 恶意 `../` ZIP 被拒绝且未在目标目录外写文件
- [ ] 磁盘不足显示 `MODEL_DISK_SPACE_INSUFFICIENT`
- [ ] 模型位于 Tauri app local data，不在安装目录

## 硬件与离线

- [ ] GPU/驱动不满足时，在加载模型前显示结构化错误
- [ ] Diagnostics 显示 App、Runtime、Model、GPU、CUDA 和 Pipeline 版本
- [ ] Diagnostics 不包含 token、用户图片/OCR 全文或私人绝对路径
- [ ] 全程断网可以启动、Ready 并完成审核
- [ ] 记录实际 GPU、VRAM、内存、驱动、Windows 版本和耗时

## 功能 GUI

- [ ] 选择普通安全图片并完成 Fast Review
- [ ] 选择风险图片并完成 Fast Review
- [ ] 完成 Deep Review
- [ ] Detection overlay 正常
- [ ] OCR overlay 正常
- [ ] Detection/OCR/VLM/技术详情 Tab 正常
- [ ] 拖放图片正常
- [ ] 主题切换正常
- [ ] Restart Runtime 后恢复 Ready
- [ ] 连续双击快捷方式只保留一个主窗口和一个 Runtime

## 进程与数据生命周期

- [ ] 关闭窗口后 `VisionGuard.exe` 退出
- [ ] 关闭窗口后 `visionguard-runtime.exe` 退出
- [ ] 重新打开后复用已安装模型
- [ ] 不产生遗留监听端口或 orphan process
- [ ] logs/artifacts/cache 均写入 app local data

## 卸载、重装与升级

- [ ] 卸载删除 App、Runtime、桌面快捷方式和 Start Menu 项
- [ ] 卸载后无 orphan process
- [ ] 默认保留模型和用户数据
- [ ] 重装自动发现 `active.json`，无需重复导入模型
- [ ] 模拟 `0.1.0 → 0.1.1` 后 Runtime 被替换
- [ ] 升级后模型、设置和 artifacts 保留
- [ ] 安装损坏/不兼容新模型时仍保留旧模型目录

## 发布门禁

- [ ] 安装器已代码签名并验证签名
- [ ] Ultralytics/detector 许可门禁解除
- [ ] CUDA/NVIDIA 再分发清单完成
- [ ] 最终 SBOM 和 THIRD_PARTY_NOTICES 与冻结包一致
- [ ] 所有 GitHub assets 小于 2 GiB 或已有正式托管/分卷方案
- [ ] `python scripts/validate_release.py <release-dir> --public` 通过

验收结论：`PASS / FAIL`　失败记录：`________________________________________`
