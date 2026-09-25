# VisionGuard Windows Release Acceptance Checklist

候选版本：`________________`　测试日期：`________________`　执行人：`________________`

必须在没有 Python、Node、Rust、源码仓库、Conda、开发虚拟环境和模型缓存的 Windows Sandbox 或干净 VM 中执行。未实际执行的项目不得勾选。

## 安装与首次启动

- [ ] 安装器 SHA-256 与 `SHA256SUMS.txt` 一致
- [ ] 断网安装成功且不要求管理员权限
- [ ] Start Menu 与桌面快捷方式存在，图标和 target 正确
- [ ] 首次启动直接发现 bundled Core Runtime / Models
- [ ] Core Ready，界面不显示命令行或 Python traceback
- [ ] 普通安全图片和风险图片均完成 Fast Review

## Advanced AI

- [ ] 选择 `advanced-ai-manifest.json` 后显示版本、大小和真实磁盘预检
- [ ] 缺卷、重复卷、错误顺序、错误大小和 SHA 篡改均 fail closed
- [ ] 安装进度与实际 I/O 字节一致
- [ ] 取消安装清理 staging，旧 active component 保持可用
- [ ] 安装完成后 VLM Runtime / Models 版本正确
- [ ] Deep Review 与 routing-triggered VLM 成功
- [ ] Runtime v1 → v2 不重新安装相同 Models
- [ ] Models v1 → v2 不重新安装相同 Runtime
- [ ] 新组件启动失败可切回 previous registry
- [ ] Remove Advanced AI 先停止 VLM，再释放磁盘；Core 仍可工作

## GUI 与进程生命周期

- [ ] Select Image 与 Drag & Drop 正常
- [ ] Detection / OCR overlay 正常
- [ ] Technical Details 与主题切换正常
- [ ] 连续双击只保留一个 Desktop、Core 和 VLM
- [ ] 点击真实窗口 X 后 Desktop、Core、VLM、端口和 GPU process 均退出
- [ ] 重开后 components 保留且无需再次导入

## Reinstall / Upgrade / Uninstall

- [ ] Desktop reinstall 自动发现已有 Advanced AI
- [ ] Desktop test version upgrade 保留 Advanced AI、设置和 artifacts
- [ ] 卸载 Desktop 默认保留用户 components
- [ ] Full uninstall 选项删除 Runtime、Models、logs、cache、settings
- [ ] 卸载后无 orphan process 或监听端口

## Offline / Hardware / Evidence

- [ ] 全程断网完成 Core 和 Advanced AI 流程
- [ ] 记录 Windows、CPU、RAM、GPU、VRAM、driver、耗时
- [ ] 截图、进程列表、端口检查和日志摘要已附到 `clean_machine_acceptance.md`
- [ ] 失败项有复现步骤，不只写 “passed”

## Release gates

- [ ] Detector 权重分发路径已解决
- [ ] CUDA / native binary 清单已逐项复核
- [ ] 最终 SBOM 与 Third-Party Notices 匹配冻结目录
- [ ] Signing 状态与 Release Notes 一致
- [ ] Historical regression 完成
- [ ] `python scripts/validate_release.py --rc` 通过

验收结论：`PASS / FAIL`　失败记录：`________________________________________`
