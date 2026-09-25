# Clean Windows Acceptance

目标是在没有源码仓库、开发工具、已有模型缓存或旧版组件残留的独立 Windows 环境验证最终候选。安装、组件/模型获取和更新阶段允许联网；审核推理必须使用本地 Runtime，不依赖云端推理 API。

## Required flow

1. 验证安装器与所有资产 SHA-256。
2. 安装、首次启动并检查 Slim Core readiness。
3. 执行 Fast Review，确认请求只到动态 loopback endpoint。
4. 获取或导入 Advanced AI，验证分卷、空间预检、原子激活和失败回滚。
5. 执行 Deep Review，确认 VLM 由本地 sidecar 提供且图片未发送到云端审核服务。
6. 验证升级、回滚、卸载、重装、无 orphan process 和日志脱敏。
7. 运行历史真实图片回归并归档截图、日志、版本、硬件与验收人。

断开网络的 Real Offline 测试是可选扩展项，不影响 RC 放行判定。
