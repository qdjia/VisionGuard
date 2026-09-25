# Clean-machine Acceptance Record

状态：**NOT EXECUTED — RC BLOCKER**  
候选版本：`1.0.0-rc.1`（尚未创建 Tag）

该记录必须在没有 Python、Node、Rust、源码仓库、Conda、开发虚拟环境和模型缓存的 Windows Sandbox 或干净 VM 中填写。开发机结果不能代替此记录。

## 环境

| 字段 | 记录 |
|---|---|
| Windows 版本 / Build | 待填写 |
| CPU / RAM | 待填写 |
| GPU / VRAM | 待填写 |
| Driver | 待填写 |
| Installer 文件名 / SHA-256 | 待填写 |
| 测试日期 / 执行人 | 待填写 |

## 验收步骤

- [ ] 断网安装 Core installer
- [ ] Start Menu 与桌面快捷方式存在，图标和 target 正确
- [ ] 双击启动，Core Ready，Fast Review 成功
- [ ] 连续双击只保留一个 Desktop / Core / VLM 实例
- [ ] 本地导入 Advanced AI manifest，显示真实字节进度
- [ ] 缺卷、篡改卷、版本不兼容均 fail closed
- [ ] 取消安装不影响旧 active component
- [ ] Advanced AI Ready，Deep Review 与 Routing-triggered VLM 成功
- [ ] 关闭窗口后 Core、VLM、端口和 GPU process 均退出
- [ ] 重开后 components 保留
- [ ] VLM Runtime / Models 独立升级、active switch 与 rollback 成功
- [ ] 移除 Advanced AI 后 Core 仍可工作
- [ ] Desktop reinstall / upgrade 保留 Advanced AI
- [ ] Full uninstall 选项删除全部用户数据（若实现）
- [ ] 卸载 VisionGuard 后无 orphan process

截图、进程列表、端口检查、日志摘要与失败项：待填写。不能只写 “passed”。
