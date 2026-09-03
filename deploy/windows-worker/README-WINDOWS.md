# Prompt Hub 5060 Ti Worker

这个目录运行在 Windows 5060 Ti 主机上。它只读取 `D:\PromptHub-Bridge\prompt-hub` 中的任务，只访问本机 `http://127.0.0.1:8188`，不需要把 ComfyUI 开放到局域网。

## 第一次运行

1. 启动 ComfyUI，并确认浏览器能打开 `http://127.0.0.1:8188`。
2. 确认已安装 Python 3.12；当前实测版本是 3.12.10。
3. 双击 `1-先自检.bat`。
4. 看到 `[OK] Worker and local ComfyUI are ready.` 后，双击 `2-启动Worker.bat`。
5. 保持 Worker 黑色窗口开启。窗口显示“等待任务”时，Mac 才能投递真实任务。

需要接入 ComfyUI LoRA Manager 时，可在 PowerShell 运行 `3-检查LoRAManager.ps1`。脚本只读取插件
源码、metadata/预览文件清单、ComfyUI 本机公开接口和 LoRA 目录统计，结果写入共享目录
`diagnostics/lora-manager-inspection.json`；它不会修改插件、下载模型或读取权重内容。

不需要安装 pip 包，不需要 Windows 密码，也不需要 API Key。`worker-config.json` 中的
`lora_roots` 只登记允许扫描的 LoRA 根目录；Mac 任务只能使用 `root_id`，不能传入任意
Windows 路径。

## 日常顺序

1. 启动 ComfyUI。
2. 双击 `2-启动Worker.bat`。
3. 在 Mac Prompt Hub 投递任务。
4. Worker 串行执行；图片与记录回到共享目录 `inbox`。
5. Mac 校验源文件和回传文件的 SHA-256，之后再进入结果审核。

## 同步 LoRA 清单

1. 保持 ComfyUI 和 Worker 运行。
2. 在 Mac Prompt Hub 的“设备连接”页点击“从 Windows 同步”。
3. Worker 读取 ComfyUI `LoraLoader` 名称、模型文件属性、同名 `.metadata.json` 和关联的封面/示例图。
4. 任务返回后，在任务卡点击“验收并导入 LoRA 清单”。
5. Mac 逐文件校验 SHA-256，保存可检索清单与独立预览缓存；不会复制 `.safetensors`。

快照不会读取权重内容，也不会为大模型计算文件 SHA-256。清单 JSON 与每张预览图分别校验；
图片限制为受支持扩展名、单张不超过 32 MiB、最多 1024 张且总计不超过 2 GiB。

## ComfyUI workflow 要求

Worker 接收的是 ComfyUI 的 **API Format workflow**，不是网页中普通的 UI workflow JSON。

生成包格式：

```json
{
  "format": "soda-comfyui-package-v1",
  "workflow_id": "anima-smoke-v1",
  "api_prompt": {
    "这里放 ComfyUI API Format 导出的完整节点对象": {}
  },
  "metadata": {
    "note": "可选说明"
  }
}
```

生成包放在：

```text
D:\PromptHub-Bridge\prompt-hub\packages\
```

Mac 投递时会在任务 manifest 中记录生成包的 SHA-256。Worker 校验一致后才会执行。

## 目录含义

- `outbox`：Mac 新投递的任务。
- `processing`：Worker 已领取或正在执行的任务。
- `inbox`：执行成功、等待 Mac 验收的结果。
- `completed`：Mac 已确认完成的任务。
- `failed`：失败或取消的任务及错误记录。

## 停止与恢复

- 正常停止：在 Worker 窗口按 `Ctrl+C`。
- 意外关机：重新启动 ComfyUI，再双击 `2-启动Worker.bat`。Worker 会恢复 `processing` 中的任务。
- 已拿到 `prompt_id` 的任务会继续查询原任务，不重新排队。
- 单机锁会阻止同时打开两个 Worker，避免一张 GPU 重复领取。

## 安全边界

- ComfyUI URL 只允许 `127.0.0.1`、`localhost` 或 `::1`。
- 任务中的相对路径不能越过共享目录。
- 所有 manifest 与输出文件都做 SHA-256 校验。
- 配置、任务、日志都不保存 SMB 密码、API Key 或 token。
- 当前执行 `comfyui_generate` 与只读 `lora_catalog_snapshot`；训练、VLM 和 Embedding 接口保留，但尚不会被这个 Worker 误执行。
