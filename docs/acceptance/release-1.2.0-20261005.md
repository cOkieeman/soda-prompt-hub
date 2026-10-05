# 1.2.0 发行验证

版本：Core、Mac 启动器、Windows Desktop 和 Compute Worker 均为 `1.2.0`。
本次发布附件与维护者验收并安装的附件一致，未重新构建或修改原生程序。

## 已验证范围

- Mac 完整测试、Ruff 格式和 lint、ty 类型检查、JavaScript 语法、锁文件一致性及 diff 检查。
- Mac App 内部 manifest、冻结源码及安装 wheel 一致；ad-hoc 签名、DMG 校验、包内 Python 和 Core health。
- 维护者验收创作台分区、导航排列、画廊红心 / 垃圾桶，以及本地和 GitHub 来源切换；宽屏与窄屏无横向溢出。
- Windows 实机编译两个 .NET 启动器和两个 Setup；12 项原生 payload 校验 fixture 通过。
- Windows 的两个完整 payload manifest、文件版本、隐私检查通过；Core 和安装 wheel 各 101 个文件与冻结源码逐一一致。
- Windows 包内 76 项隔离运行验证：最终 Prompt / 实际 LoRA 记录、异常 JSON 数值、图片元数据和本地 / GitHub 来源选择。
- Windows 单机 Core、本机 Worker、独立 Worker 均启动；ComfyUI 可连接；Mac 与独立 Worker 的共享、心跳及协议兼容正常。
- 实机更新采用验证过的程序目录，更新前后核对已有图库原图、缩略图、个人记录与配置，内容保留；桌面快捷方式更新成功。
- 三端附件 SHA-256 核对通过；发行目录不含私人图片、数据库、真实 Worker 配置、凭据或模型权重。

## 本次未验证的范围

- 未在维护者真实数据上执行 Windows Setup 的覆盖安装、卸载及重装；实际更新使用与安装器相同构建阶段的 verified payload。
- 未独立解压 Inno Setup 内嵌文件；安装器与验证 payload 的对应关系来自同一已完成构建阶段及 manifest。
- 未提交新一轮真实 GPU 图像生成或 LoRA 训练。
- 不宣称完成新版 Linux 原生部署验收，Linux 仍为实验性支持。
- Windows 产品安装器未作 Authenticode 签名；Mac 仅 ad-hoc 签名，未 Developer ID 签名或公证。

安装包因此标为 Pre-release；软件内的 `1.2.0 / stable` 是运行时通道，不代表所有安装与签名验收完成。

## 升级

备份个人资料，退出旧程序并停止所属服务，再替换或安装对应组件；从新快捷方式启动。程序与资料分离，
不需要删除资料库、模型、LoRA、画风库或 ComfyUI。Windows 单机已管理本机 Worker，不需要同时启动独立 Worker；Mac 双机模式使用独立 Worker。

从 [1.2.0 Release](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0) 下载附件，并按 `SHA256SUMS.txt` 核对下载文件。
