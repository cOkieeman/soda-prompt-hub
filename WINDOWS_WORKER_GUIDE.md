# 5060 Ti Windows Worker 交付说明

## 当前闭环

```text
Mac Prompt Hub
  → /Volumes/PromptHub-5060Ti/prompt-hub/outbox
  → Windows worker 原子领取到 processing
  → Windows 本机 ComfyUI 127.0.0.1:8188
  → 图片、API workflow、运行记录写入 inbox/{task_id}
  → 结果信封写入 inbox/{task_id}.json
  → Mac 对源文件与全部输出做 SHA-256 验收
```

Mac 是项目、任务和审核的事实源；Windows 只负责计算。ComfyUI 不需要监听局域网地址。

同一个 Worker 也支持只读 `lora_catalog_snapshot`：它读取 ComfyUI `LoraLoader` 名称、配置白名单
内的模型文件属性、同名 `.metadata.json` 与关联预览图，再回传清单 JSON 和独立图片输出。每个文件
都有大小与 SHA-256，Mac 验收后才写入本机缓存。它不读取权重内容，也不把 `.safetensors` 复制到 Mac。

## 配置示例

- Windows：`<Windows 主机名>` / `<局域网 IP>`
- Python：3.12.10
- ComfyUI：`http://127.0.0.1:8188`
- 共享根：`D:\PromptHub-Bridge`
- Worker bridge：`D:\PromptHub-Bridge\prompt-hub`
- Mac 挂载：`/Volumes/PromptHub-5060Ti`
- Mac bridge：`/Volumes/PromptHub-5060Ti/prompt-hub`

## 首次部署顺序

1. Mac 把 worker 包同步到共享目录 `prompt-hub/worker`。
2. Windows 打开 `D:\PromptHub-Bridge\prompt-hub\worker`。
3. 保持 ComfyUI 正常运行。
4. 双击 `1-先自检.bat`。
5. 自检成功后，双击 `2-启动Worker.bat` 并保持窗口开启。
6. Mac 读取 `worker-status.json`，确认设备名、Python、协议和 ComfyUI 连通性。
7. 从 Windows ComfyUI 导出一个低成本 workflow 的 **API Format** JSON。
8. 将 workflow 包装成 `soda-comfyui-package-v1`，由 Mac 写入 manifest 后投递。
9. Worker 出图回传；Mac 调用任务 `integrity` 接口验收。

## 内置烟雾测试

仓库自带 `deploy/windows-worker/examples/comfyui-smoke-empty-image-v1.json`。它只调用
ComfyUI 内置的 `EmptyImage → SaveImage`，生成一张 128×128 蓝色 PNG，不加载 checkpoint。
它用于快速验证 Worker、ComfyUI、图片下载、inbox 回传和 SHA-256 验收，不代表 Anima / Krea 2
模型质量测试。

2026-09-02 已在目标 5060 Ti Windows 主机完成真实验收：任务正常 returned，图片、API workflow
与 run log 共 3 个输出通过 Mac 完整性校验。

## 每日使用顺序

```text
先开 ComfyUI → 再开 Worker → 最后在 Mac 投递
```

关机前可在 Worker 窗口按 `Ctrl+C`。如果异常中断，下一次启动会恢复 processing 中的任务。

当前 ComfyUI 状态报告显示启动参数包含 `--listen 0.0.0.0`。Worker 只访问
`127.0.0.1:8188`，因此完成现有浏览器用途核对后，应将 ComfyUI 收紧为本机监听并复验 Worker，
避免把 8188 暴露到局域网。

## 当前完成边界

本轮 Worker 启用 `comfyui_generate` 和只读 `lora_catalog_snapshot`。仍待接入：

1. LoRA smoke test / 正式训练；
2. 批量 VLM caption；
3. CLIP/SigLIP embedding。

这些任务仍共用单 GPU 串行锁，不会与 ComfyUI 出图并发抢显存。
