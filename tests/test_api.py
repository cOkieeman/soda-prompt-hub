from __future__ import annotations

import json

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_all


def test_api_health_stats_search_and_page(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    app = create_app(source_tree)

    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/stats").json()["entries"] > 5
        assert len(client.get("/api/sources").json()) == 4
        result = client.get("/api/search", params={"query": "gothic", "kind": "style"})
        assert result.status_code == 200
        assert result.json()["results"][0]["title"] == "Gothic Ink"
        assert result.json()["results"][0]["visuals"][0]["thumbnail_url"]
        clio_media = client.get(result.json()["results"][0]["visuals"][0]["thumbnail_url"])
        assert clio_media.status_code == 200
        kisega = client.get("/api/search", params={"query": "collared shirt", "kind": "tag"})
        thumbnail_url = kisega.json()["results"][0]["visuals"][0]["thumbnail_url"]
        assert client.get(thumbnail_url).headers["content-type"] == "image/webp"
        assert client.get(thumbnail_url.replace("thumbnail", "original")).status_code == 200
        assert client.get("/media/kisegaeningyou/original/../test.sqlite").status_code == 404
        suggestive = client.get(
            "/api/search",
            params={"query": "underboob", "kind": "tag", "safety": "suggestive"},
        ).json()["results"][0]
        assert suggestive["visuals"][0]["safety"] == "suggestive"
        mark_response = client.put(
            "/api/marks",
            json={
                "source_id": "clio-style-preview",
                "external_id": "style:0",
                "favorite": True,
                "rating": 5,
                "note": "Keep this <reference>",
            },
        )
        assert mark_response.status_code == 200
        assert mark_response.json()["user_rating"] == 5
        favorites = client.get("/api/search", params={"favorites_only": True}).json()
        assert favorites["count"] == 1
        assert favorites["results"][0]["user_note"] == "Keep this <reference>"
        assert client.get("/api/stats").json()["personal"]["favorites"] == 1
        assert (
            client.put(
                "/api/marks",
                json={"source_id": "missing", "external_id": "missing", "favorite": True},
            ).status_code
            == 404
        )
        assert (
            client.put(
                "/api/marks",
                json={"source_id": "clio-style-preview", "external_id": "style:0", "rating": 6},
            ).status_code
            == 422
        )
        page = client.get("/")
        assert page.status_code == 200
        assert (
            '<section class="creative-subsection" id="creativeResultsSection">\n'
            '        <div class="creative-subsection-head"><h2>检查生成结果</h2>'
        ) in page.text
        assert "Soda Prompt Archive" in page.text
        assert "开始创作" in page.text
        assert "提示词库" in page.text
        assert "角色库" in page.text
        assert "资料管理" in page.text
        assert "今天想画" in page.text
        assert "ANIMA" in page.text
        assert "KREA 2" in page.text
        assert "高级筛选" in page.text
        assert "维多利亚军装" in page.text
        assert "绘图创作" in page.text
        assert "把画面拆成七部分" in page.text
        assert "从提示词库找参考" in page.text
        assert "找到的参考资料" in page.text
        assert all(
            (marker[1:] not in page.text if marker.startswith("!") else marker in page.text)
            for marker in (
                "检查生成结果",
                "resultImageFile",
                "visionModel",
                "只写入实测备注",
                "由此创建下一版",
                "lineageNotice",
                "本轮迭代对照",
                "applyIterationSuggestions",
                "加入数据集",
                "datasetProfile",
                "WD14 · 生成 Anima 标签草稿",
                "tagSelectedDataset",
                "data-wd14-tag",
                "导出精选数据集 ZIP",
                "数据集工作台",
                "datasetImportForm",
                ".dataset-workspace-list { min-width: 0;",
                (
                    ".dataset-workspace-item { width: 100%; min-width: 0; "
                    "max-width: 100%; overflow: hidden;"
                ),
                "datasetJourney",
                'data-dataset-step="1"',
                'data-dataset-step="5"',
                "导入素材",
                "检查问题",
                "准备标签",
                "人工审核",
                "生成交付版本",
                "datasetModeSimple",
                "datasetModeAdvanced",
                "datasetDeliveryProfile",
                "datasetReadiness",
                "datasetNextAction",
                "datasetDeliveryPanel",
                "datasetPreflight",
                "datasetExportActiveProfile",
                "datasetDeliveryHistory",
                "复制到 5060 Ti",
                "打开 Finder",
                "hashes.sha256",
                "不修改源文件夹",
                "不会启动 Windows 训练",
                "function deliveryState()",
                "function renderJourney()",
                "datasetPagination",
                "pageSize: 200",
                "loraPage",
                "loraCreateForm",
                "Windows 出图",
                "comfyFileForm",
                "comfyDirectoryForm",
                "sourceSyncButton",
                "更新公共提示词库",
                "设备连接",
                "remoteSectionTabs",
                'role="tablist"',
                'data-remote-view="tasks"',
                'data-remote-view="loras"',
                'data-remote-view="models"',
                "remoteTasksPanel",
                "remoteLoraPanel",
                "remoteModelPanel",
                'aria-selected="true"',
                "remoteNodeGrid",
                "任务状态",
                "这里会出现哪些任务",
                "这里只记录 Mac 与 5060 Ti 之间的出图和模型清单更新",
                "更新 LoRA 清单",
                "更新底模清单",
                "ComfyUI 出图",
                "等待你接收结果",
                "查看技术信息",
                "任务编号",
                "第 ${item.attempt||1} 次投递",
                "执行程序",
                "失败原因",
                "remoteTaskSummary",
                "条历史记录",
                "条需要处理",
                "remoteTaskList",
                "查看 Windows 上的 LoRA",
                "来自 LoRA Manager",
                "remoteLoraSync",
                "remoteLoraTree",
                "LoRA 目录树",
                "data-lora-tree-toggle",
                "data-lora-category",
                "remoteLoraResultStatus",
                "当前筛选没有结果",
                "接收 LoRA 清单",
                "import-lora-catalog",
                "await loadLoras($('#remoteLoraQuery').value.trim())",
                "remotePreviewDialog",
                "remote-lora-preview",
                "preview_urls",
                "暂无本地预览图",
                "查看 Windows 上的模型",
                "remoteModelSync",
                "remoteModelTree",
                "模型类型与目录树",
                "data-model-tree-toggle",
                "接收底模清单",
                "import-model-catalog",
                "await loadModels($('#remoteModelQuery').value.trim())",
                "tagLanguageToggle",
                "datasetTagSuggestions",
                "datasetSourceCaptionProfile",
                "/source-captions/preview",
                "prepareTagLabels",
                "coverageLabel",
                "loraCoveragePreview",
                "/coverage/preview",
                "workflowProfile",
                "workflowLowCost",
                "workflowControlList",
                "workflowSampler",
                "workflowScheduler",
                "workflowLoraRows",
                "workflowAddLora",
                "workflowLoraPicker",
                "workflowLoraSearch",
                "workflowLoraFolder",
                "data-workflow-lora-pick",
                "workflow-model-visual",
                "data-model-preview",
                "item.metadata?.civitai_model_id",
                "item.metadata?.civitai_version_id",
                "item.source_url",
                "查看 Civitai",
                "source_url",
                "genWidth",
                "genHeight",
                "workflow_controls",
                "sendWorkflow",
                "发送到 5060 Ti",
                "projectJourneyGrid",
                "creativeResultsSection",
                "从想法到数据集",
                "syncProjectDataset",
                "/dataset-workspace",
                "openCreativeProject",
                "openDatasetWorkspace",
                "外部独立数据集",
                "返回来源项目",
                "接收并导入图片",
                "/api/workflow-tasks/",
                "const workspaceStatusLabels",
                "等待扫描",
                "正在扫描",
                "可使用",
                "扫描失败",
                "const remoteStateLabels",
                "Windows 已就绪",
                "共享目录未挂载",
                "需要创建任务文件夹",
                "共享目录不可写",
                "Python /",
                "设备 /",
                "导入失败:",
                "保存失败:",
                "读取失败:",
                "暂无版本",
                "!Drawing Desk",
                "!>LOCKED<",
                "!>UNLOCKED<",
                "!>REMOVE<",
                "!Library Status",
                "!跨设备任务状态",
                "!Mac 已记录",
                "!ComfyUI LoRA 远程清单",
                "!ComfyUI model folders / metadata only",
            )
        )
        assert "导出 Anima + Krea 2 JSON" in page.text
        assert "data-creative-add" in page.text


def test_page_uses_scoped_headers_and_accessible_contrast(settings) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        page = client.get("/")

    assert page.status_code == 200
    assert page.text.count('class="output-block-head"') == 2
    assert ".output-block header" not in page.text
    assert ".output-block-head {" in page.text
    assert '<header class="archive-header">' in page.text
    assert "    header {" not in page.text
    assert "--muted: #5b5a53;" in page.text
    assert "--signal: #a33822;" in page.text
    assert ".comfy-head .section-label, .comfy-head label { color: #b9ae9f; }" in page.text


def test_compute_contract(settings) -> None:
    with TestClient(create_app(settings)) as client:
        compute = client.get("/api/compute/contract").json()
        assert compute["protocol_version"] == "soda-compute-bridge-v2"
        capabilities = compute["roles"]["compute_5060ti"]["capabilities"]
        assert {"comfyui_generate", "lora_train", "embedding_batch"} <= set(capabilities)
        assert compute["task_types"]["comfyui_generate"]["target_role"] == "compute_5060ti"
        assert compute["security"]["credentials_in_tasks"] is False
        assert compute["security"]["model_outputs_require_review"] is True
        assert "returned" in compute["task_states"]
        assert "retry_of" in compute["task_envelope"]["optional"]
        assert compute["task_types"]["embedding_batch"]["item_required"][-1] == "sha256"
        assert compute["task_types"]["vlm_caption_batch"]["constraints"] == {
            "profile_id": "krea2",
            "language": "en",
            "result": "draft",
        }
        assert compute["task_types"]["model_catalog_snapshot"]["constraints"] == {
            "read_only": True,
            "copy_weights_to_mac": False,
            "read_weight_contents": False,
            "hash_weight_contents": False,
            "model_roots": "root_id values from Windows Worker configuration",
            "paths": "relative_to_configured_windows_root",
        }


def test_api_rebuild_index(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    app = create_app(source_tree)
    with TestClient(app) as client:
        response = client.post("/api/import")
        assert response.status_code == 200
        assert response.json()["stats"]["sources"] == 4


def test_api_imports_and_searches_oc_manager_json(settings) -> None:
    app = create_app(settings)
    export = {
        "format": "oc-manager-full-database",
        "characters": [
            {
                "id": "char-api",
                "name": "阿莉娅",
                "world": "镜海",
                "race": "人类",
                "story": "调查沉没图书馆",
                "prompts": [{"id": "p1", "label": "portrait", "text": "silver eyes"}],
            }
        ],
        "worlds": [{"id": "world-api", "name": "镜海", "system": "generic"}],
        "lore": {"镜海": {"locations": [{"id": "l1", "name": "沉没图书馆"}]}},
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/oc-manager/import",
            params={"filename": "oc-backup.json"},
            content=json.dumps(export, ensure_ascii=False).encode(),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["characters_imported"] == 1
        assert response.json()["stats"]["characters"] == 1
        archived = settings.oc_imports_root / response.json()["source_file"].split("/")[-1]
        assert archived.exists()

        search = client.get(
            "/api/oc-manager/characters",
            params={"query": "图书馆", "world": "镜海"},
        ).json()
        assert search["count"] == 1
        assert search["results"][0]["name"] == "阿莉娅"
        profile = client.get("/api/oc-manager/characters/char-api")
        assert profile.status_code == 200
        assert profile.json()["prompts"][0]["text"] == "silver eyes"
        assert client.get("/api/oc-manager/characters/missing").status_code == 404
        assert client.get("/api/oc-manager/worlds").json()[0]["character_count"] == 1
        lore = client.get("/api/oc-manager/lore", params={"query": "沉没"}).json()
        assert lore["count"] == 1
        assert client.get("/api/stats").json()["oc_manager"]["characters"] == 1

        invalid = client.post(
            "/api/oc-manager/import",
            params={"filename": "broken.json"},
            content=b"broken",
        )
        assert invalid.status_code == 422
