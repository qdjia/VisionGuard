# Fresh-user GUI Acceptance

本验收由用户手动执行。不要用 `python main.py`、`npm run dev`、`tauri dev` 或源码 Runtime
替代真正的候选安装器。

## 准备

1. 在开发账户预先记录候选安装器 SHA-256，并把安装器放到新用户可访问的普通目录。
2. 打开 Windows **设置 → 账户 → 其他用户 → 添加账户**。
3. 选择“我没有此人的登录信息”与“添加没有 Microsoft 账户的用户”（不同 Windows 版本文字可能略有差异）。
4. 创建普通用户，不授予管理员角色，不为其安装 Python、Conda、Node、Rust 或开发工具。
5. 登录新用户，确认它不能访问开发用户 AppData、HF cache 或源码目录。

## 安装与首次启动

1. 双击真正的 `VisionGuard-Setup-<version>.exe`，完成安装。
2. 记录 Desktop shortcut 和 Start Menu entry 是否存在。
3. 双击启动，确认无需控制台、手工端口或外部浏览器。
4. 等待 Core 状态到 Ready；检查日志不存在源码盘、开发用户 home、Anaconda 或旧 VLM 路径。
5. 确认 Advanced AI 显示 `Not Installed`，安装按钮存在；本 Gate 不要求完成大模型下载。

## GUI 与 Fast Review

1. 使用原生文件选择器打开一张 safe image。
2. 如果产品支持拖拽，再拖入一张图片。
3. 分别执行一张 safe 和一张 risky 图片的 Fast Review。
4. 检查 Detection overlay、OCR、Routing、Fusion、Review status、risk 与 timing 正常渲染。
5. 确认 OCR/理由文本没有按原始 HTML 执行，界面无崩溃或明显布局破坏。
6. 连续打开应用两次，确认单实例行为符合设计。

## 生命周期

1. 关闭窗口，确认没有遗留 `VisionGuard.exe`、Core Runtime 或 VLM Runtime。
2. 重新启动，确认 Core 再次 Ready。
3. 从 Windows 设置卸载，确认应用目录、Desktop shortcut 和 Start Menu entry 被移除。
4. 用户数据可以按产品策略保留，但必须记录实际行为。
5. 重新安装一次并确认可以启动。

## Evidence

填写 `release-evidence/fresh-user-gui.json`：

- 不写用户名、home 绝对路径或截图中的隐私信息；
- 填候选 hash、Windows 版本、普通用户类型、各步骤状态和备注；
- 截图建议包括安装完成、Core Ready、Fast Review、Advanced AI Not Installed 和卸载完成；
- 未执行的步骤保持 `NOT_EXECUTED`，Gate 状态保持 BLOCKED。

只有所有 required checks 均 PASS，才可把顶层 `status` 改为 PASS。

