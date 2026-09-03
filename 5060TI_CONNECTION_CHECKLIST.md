# 5060 Ti Windows 设备连接与配合清单

更新时间：2026-09-02

## 一、设备分工

### MacBook Air

负责：

- Prompt Hub 项目与创作资料管理
- OC、提示词库和数据集整理
- Prompt、Caption 和 WD14 标签审核
- LoRA 项目规划、数据集冻结和版本记录
- Windows 任务编排、状态记录、结果审核和失败重试
- Embedding、VLM Caption 和 LoRA 清单的最终索引

### 5060 Ti 16GB Windows

负责：

- ComfyUI 制图与批量测试
- LoRA smoke test、正式训练和 checkpoint 测试
- WD14 批量打标
- CLIP/SigLIP Embedding 批处理
- Krea 2 VLM Caption 批处理
- Windows Worker 读取 LoRA Manager metadata 与 ComfyUI LoRA 目录

5060 Ti 只有一张 GPU，因此 GPU 任务默认串行执行：

1. 不自动抢占正在运行的 LoRA 训练。
2. LoRA 训练和 ComfyUI 制图互斥。
3. WD14、Embedding 和 VLM Caption 只在 GPU 空闲时执行。

---

## 二、当前状态

Mac 端已经完成：

- 单一 `compute_5060ti` 节点协议
- ComfyUI、LoRA、WD14、Embedding、VLM 和 LoRA 清单任务接口
- SMB 共享目录诊断与五目录初始化
- Mac 侧任务记录、状态扫描和失败重试
- 凭据字段拦截和源文件 SHA-256 回验
- 设备连接页面单节点改造

尚未完成：

- Windows SMB 真实挂载
- Windows worker 安装与启动
- ComfyUI 和训练工具实际调用
- LoRA Manager/ComfyUI LoRA 目录的真实读取与清单同步
- 跨设备断线恢复验收

---

## 三、Windows 第一次准备

### 1. 查看设备名称

在 Windows 打开：

```text
设置 → 系统 → 系统信息 → 设备名称
```

记录设备名称，不需要修改。

### 2. 查看局域网 IPv4

在 Windows 打开：

```text
设置 → 网络和 Internet → 当前网络 → 属性 → IPv4 地址
```

建议后续在路由器中为这台设备设置 DHCP 地址保留，避免 IP 经常变化。第一次连接时可以先使用当前 IPv4。

### 3. 确认网络类型

当前局域网应设置为：

```text
专用网络
```

不要在不可信公共网络中开启共享。

### 4. 开启局域网共享能力

在 Windows 的“高级网络设置”或“高级共享设置”中开启：

- 网络发现
- 文件和打印机共享

只需要对专用网络开启。

---

## 四、建立 Prompt Hub 共享目录

建议建立：

```text
D:\PromptHub-Bridge
```

如果没有 D 盘，可以使用其他数据盘，但不要放在临时目录或 ComfyUI 安装目录内。

### 共享设置

1. 右键 `D:\PromptHub-Bridge`。
2. 打开“属性 → 共享 → 高级共享”。
3. 勾选“共享此文件夹”。
4. 共享名填写：

```text
PromptHub-5060Ti
```

5. 给日常使用的 Windows 用户配置读取和写入权限。
6. 同时检查“安全”标签页，确保该用户对真实文件夹也有读取和写入权限。

不建议给 `Everyone` 开放完全控制；优先只授权自己的 Windows 用户。

---

## 五、需要提供的非敏感信息

填写后将下面内容发给 Codex：

```text
设备名称：
局域网 IPv4：
SMB 共享名：PromptHub-5060Ti
共享目录实际路径：D:\PromptHub-Bridge

ComfyUI 根目录：
ComfyUI output 目录：

LoRA 训练工具名称：
LoRA 训练工具目录：
底模目录：
LoRA 模型目录：
LoRA Manager 插件目录：
```

LoRA 训练工具名称示例：

- kohya_ss
- OneTrainer
- ai-toolkit
- Musubi Tuner
- 其他工具

如果无法判断某个目录，可以发送资源管理器截图，不要发送密码或密钥内容。

---

## 六、绝对不要发到聊天里的内容

不要将以下信息写入聊天、任务 JSON、Git 仓库或 SQLite：

- Windows 登录密码
- Microsoft 账户密码
- GitHub Token
- API Key
- SSH 私钥
- `.env` 文件内容
- 浏览器 Cookie
- 其他访问凭据

Windows 用户名可以提供，密码必须由本人在 macOS 或 Windows 的系统凭据窗口中输入。

Windows Hello PIN 通常不是 SMB 密码。挂载 SMB 时一般需要对应账户的真实密码。

---

## 七、在 Mac 挂载 Windows 共享目录

完成 Windows 共享后，在 Mac 上：

1. 打开 Finder。
2. 选择“前往 → 连接服务器”。
3. 输入：

```text
smb://Windows的IPv4/PromptHub-5060Ti
```

示例：

```text
smb://192.168.1.50/PromptHub-5060Ti
```

4. 选择注册用户。
5. 本人输入 Windows 用户名和密码。
6. 可以选择将凭据保存到 macOS 钥匙串。

成功后，Mac 通常会出现：

```text
/Volumes/PromptHub-5060Ti
```

如果系统自动在名称后增加数字，应把 Finder 实际挂载路径告诉 Codex，不要自行猜测。

---

## 八、Prompt Hub 登记与目录初始化

SMB 挂载成功后，在 Prompt Hub 的“设备连接”页面登记：

```text
节点：compute_5060ti
显示名：5060 Ti · 制图与炼丹节点
主机名或 IP：Windows 实际设备名或 IPv4
Mac SMB 挂载目录：/Volumes/PromptHub-5060Ti
```

随后依次执行：

1. 保存登记
2. 检查挂载
3. 建立交付目录

系统会在共享目录中建立：

```text
outbox
inbox
processing
completed
failed
```

这些目录的作用：

- `outbox`：Mac 等待 Windows 领取的任务
- `processing`：Windows 已领取或正在执行的任务
- `inbox`：Windows 返回、等待 Mac 审核的结果
- `completed`：已经完成并确认的任务
- `failed`：失败记录和错误报告

Mac 仍然是项目、审核和任务状态的事实源。Windows 返回内容不会未经审核直接覆盖项目。

---

## 九、Windows worker 接入顺序

不要一开始同时接入所有功能。建议按以下顺序逐项证明：

### 阶段 1：共享目录读写

- Mac 能建立五个交付目录
- Windows 能读取 Mac 创建的测试文件
- Windows 能写入测试结果
- Mac 能重新读取结果

### 阶段 2：ComfyUI 最小任务

- 投递一个低分辨率、单张、固定 seed 的测试任务
- Windows 调用 ComfyUI
- 回传图片、workflow、PNG metadata 和运行日志
- Mac 验证文件哈希并进入人工审核

### 阶段 3：ComfyUI LoRA 远程清单

- 只读取 LoRA metadata
- 导出名称、路径、底模、trigger、标签和预览图位置
- Mac 不复制 LoRA 权重，只保存可检索清单

### 阶段 4：LoRA smoke test

- 使用冻结数据集和测试配置
- 只训练 5–10 step
- 验证训练工具、显存、日志和 checkpoint 回传
- smoke test 通过后再安排正式训练

### 阶段 5：批处理能力

- WD14 批量打标
- CLIP/SigLIP Embedding
- Krea 2 VLM Caption
- 队列暂停、恢复和失败重试

### 阶段 6：稳定性

- Windows worker 重启
- SMB 短暂断线
- 相同任务避免重复执行
- 失败任务保留旧记录并创建新的 retry 任务

---

## 十、日常工作流程

### ComfyUI 制图

```text
Mac 整理角色、提示词和参考图
→ 导出 ComfyUI 任务包
→ 5060 Ti 生成图片
→ 图片和 metadata 回传 Mac
→ Mac 人工筛选、复盘和建立下一版本
```

### LoRA 炼丹

```text
Mac 整理与审核数据集
→ 冻结训练数据和配置
→ 5060 Ti 执行 smoke test
→ Mac 审核样图与日志
→ 5060 Ti 正式训练
→ checkpoint 与测试图回传
→ Mac 记录版本、底模、trigger 和结论
```

### 数据集 Caption 与检索

```text
Mac 建立工作区和扫描清单
→ GPU 空闲时交给 5060 Ti 批处理
→ Windows 返回 WD14 / Embedding / VLM 草稿
→ Mac 回验源文件哈希
→ 人工确认后进入正式数据集或检索索引
```

---

## 十一、第一次连接验收标准

只有满足以下条件，才视为 5060 Ti 已正式接入：

- Prompt Hub 只登记一个 `compute_5060ti` 节点
- SMB 挂载和五目录读写正常
- 凭据没有进入任务文件或项目仓库
- ComfyUI 最小任务成功回传
- Windows Worker 成功读取 LoRA Manager metadata 与 ComfyUI LoRA 目录
- LoRA 5–10 step smoke test 成功
- Mac 能验证任务 ID、源文件哈希和输出哈希
- 训练期间不会同时启动 ComfyUI GPU 任务
- worker 或网络中断后任务不会无记录丢失

---

## 十二、遇到问题时需要记录什么

发生连接或执行问题时，只需要记录：

```text
发生时间：
正在执行的任务类型：
Prompt Hub 页面显示状态：
Windows worker 显示状态：
SMB 是否仍可打开：
错误消息或截图：
是否正在训练：
```

不要反复点击“重新投递”。先确认当前任务是否已经被 Windows 领取，避免产生重复生成或重复训练。
