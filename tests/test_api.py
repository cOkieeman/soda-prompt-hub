from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from prompt_hub import __version__, api, local_model
from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_all
from prompt_hub.model_connections import ModelConnection


def test_home_uses_configured_device_name_without_script_injection(settings) -> None:
    with TestClient(create_app(settings)) as client:
        default_page = client.get("/").text
        assert "Windows 绘图设备" in default_page
        assert "__PROMPT_HUB_DEVICE_NAME_" not in default_page

        saved = client.put(
            "/api/remote-nodes/compute-5060ti",
            json={"label": "绘图机 </script>&", "role": "compute_5060ti"},
        )
        assert saved.status_code == 200

        configured_page = client.get("/").text
        assert "绘图机 &lt;/script&gt;&amp;" in configured_page
        assert 'let remoteDeviceName = "绘图机 \\u003c/script\\u003e\\u0026";' in configured_page
        assert "__PROMPT_HUB_DEVICE_NAME_" not in configured_page


def test_api_health_stats_search_and_page(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    app = create_app(source_tree)

    with TestClient(app) as client:
        assert ((health := client.get("/api/health").json())["status"], health["service"]) == (
            "ok",
            "soda-prompt-hub",
        )
        assert client.get("/api/stats").json()["entries"] > 5
        assert len(client.get("/api/sources").json()) == 5
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
        assert "Soda Prompt Hub" in page.text
        assert "开始创作" in page.text
        assert "提示词库" in page.text
        assert "角色库" in page.text
        assert "资料来源" in page.text
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
                "资料管理",
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
                "需要交付的数据集格式",
                "loraDeliveryReadiness",
                "datasetModeSimple",
                "datasetModeAdvanced",
                "datasetDeliveryProfile",
                "datasetReadiness",
                "datasetNextAction",
                "datasetDeliveryPanel",
                "datasetPreflight",
                "datasetExportActiveProfile",
                "datasetDeliveryHistory",
                "复制到 ${escapeHtml(target)}",
                "打开 Finder",
                "hashes.sha256",
                "不修改源文件夹",
                "不会启动 Windows 训练",
                "function deliveryState()",
                "function renderJourney()",
                "datasetPagination",
                "pageSize: 24",
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
                "homeProgramVersion",
                "homeDataVersion",
                "homeReleaseIdentity",
                "homeFirstGuide",
                "/api/system/version",
                "data-remote-worker-version",
                "Worker 需要更新",
                "当前 Worker 无法与本版通信",
                "任务状态",
                "这里会出现哪些任务",
                "data-remote-device-name",
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
                "remoteTaskMore",
                "收起较早的",
                "remoteCancelQueued",
                "取消全部等待中的任务",
                "状态待确认",
                "等待连接 Windows 后核对",
                "条历史记录",
                "条需要你处理",
                "当前任务",
                "旧清单任务已收起",
                "已被较新的清单取代",
                "正在检查文件…",
                "正在接收 LoRA…",
                "正在接收底模…",
                "正在接收图片…",
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
                "发送到 <span data-remote-device-name>",
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


def test_openapi_reports_public_release_version(settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/openapi.json").json()["info"]["version"] == __version__


def test_api_exposes_selected_tagger_calibration(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/tagger-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_id"] == "wd-swinv2-tagger-v3"
    assert payload["id"] == "wd-swinv2-tagger-v3"
    assert [model["id"] for model in payload["models"]] == [
        "wd-swinv2-tagger-v3",
        "idolsankaku-swinv2-tagger-v1",
    ]
    assert payload["models"][0] == {
        "id": "wd-swinv2-tagger-v3",
        "label": "二次元与插画",
        "model": "SmilingWolf/wd-swinv2-tagger-v3",
        "general_threshold": 0.35,
        "character_threshold": 0.85,
        "available": False,
    }
    assert payload["models"][1]["label"] == "真人与摄影"
    assert payload["models"][1]["general_threshold"] == 0.3094


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


def test_page_has_mobile_menu_and_workspace_resume_entry(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/")

    assert page.status_code == 200
    assert 'id="appNavToggle"' in page.text
    assert 'aria-controls="appNavItems"' in page.text
    assert 'id="appNavCurrent"' in page.text
    assert '.app-nav[data-menu-open="true"] .app-nav-items' in page.text
    assert "@media (max-width: 1400px) and (min-width: 901px)" in page.text
    assert "setNavMenu(false);" in page.text
    assert 'id="datasetContinue" hidden' in page.text
    assert 'id="datasetContinueButton"' in page.text
    assert "hasWorkspaces?'导入另一个文件夹':'01 · 导入素材'" in page.text
    assert "deliveryState().recommended" in page.text


def test_home_offers_batch_setup_for_missing_recommended_sources(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text

    for marker in (
        'id="homeSourceSetup"',
        'id="homeSourceInstall"',
        'id="homeSourceSkip"',
        'id="homeSourceProgress"',
        "sourceSetupSkipKey",
        "renderHomeSourceSetup(sources)",
        "source_ids: sourceIds, clone_missing: true",
        "loadSourceSyncStatus(), searchPrompts()",
        "许可证待查",
        "视觉参照库图片较多",
    ):
        assert marker in page


def test_remote_page_auto_diagnoses_saved_nodes_and_after_save(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text

    assert "function renderDiagnostic(card,result)" in page
    assert "function diagnoseNode(card,nodeId)" in page
    assert "function diagnoseSavedNodes()" in page
    assert "await diagnoseNode(card,nodeId); return;" in page
    assert "diagnoseSavedNodes(),loadCatalogCounts()" in page
    assert "正在自动检查共享目录与 Worker 状态" in page
    assert "暂时无法检查设备" in page


def test_page_paginates_long_lists_and_loads_model_tabs_on_demand(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text

    for marker in (
        'id="archivePagination"',
        "archivePageSize = 12",
        "renderPromptPage()",
        "pageSize: 24",
        "workspacePageSize()",
        'id="loraJourney"',
        'data-lora-step="3"',
        'id="loraPagination"',
        "assetPageSize:12",
        "sourcePageSize:12",
        "renderSourceImages",
        "state.sourceSelected",
        "renderCoverageEditor",
        'id="remoteLoraPagination"',
        'id="remoteModelPagination"',
        "catalogPageSize()",
        "ensureRemoteViewData",
    ):
        assert marker in page
    assert "await Promise.all([loadLoras(),loadModels(),loadTasks()])" not in page
    assert "project.assets.map(assetCard)" not in page


def test_page_persists_dataset_selection_and_lora_status_changes(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text

    assert "async function clearDatasetSelection()" in page
    assert "selected:button.dataset.bulkStatus!=='excluded'" in page
    assert "async function saveAssetStatus(card)" in page
    assert "jsonOptions({status:select.value})" in page
    assert "data-asset-save-status" in page


def test_rebuild_index_reports_progress_in_source_center(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text

    assert "const sourceMessage = $('#sourceSyncMessage')" in page
    assert "sourceMessage.textContent = '正在重建本地索引…'" in page
    assert "sourceMessage.textContent = message" in page
    assert "sourceMessage.textContent = `重建失败：${error.message}`" in page  # noqa: RUF001


def test_fixed_interaction_messages_have_english_translations(settings) -> None:
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text

    for marker in (
        "Currently searching the local library by keyword.",
        "Searched the local library by keyword and related meaning.",
        "The current semantic index cannot be used for this query",
        "Rebuilding the local index…",
        "Saving…",
        "Saved",
        "Rebuild failed:",
    ):
        assert marker in page


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


def test_animadex_visual_search_and_facets(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    with TestClient(create_app(source_tree)) as client:
        animadex = client.get(
            "/api/search",
            params={
                "source_id": "animadex",
                "has_visual": True,
                "hair_color": "silver hair",
                "eye_color": "blue eyes",
            },
        ).json()
        assert animadex["count"] == 1
        animadex_thumb = animadex["results"][0]["visuals"][0]["thumbnail_url"]
        assert client.get(animadex_thumb).headers["content-type"] == "image/webp"
        assert animadex["results"][0]["visuals"][0]["original_url"] == animadex_thumb
        facets = client.get("/api/sources/animadex/facets").json()
        assert facets["categories"] == ["test_series"]
        assert facets["hair_colors"] == ["silver hair"]
        assert facets["eye_colors"] == ["blue eyes"]


def test_api_rebuild_index(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    app = create_app(source_tree)
    with TestClient(app) as client:
        response = client.post("/api/import")
        assert response.status_code == 200
        assert response.json()["stats"]["sources"] == 5


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


class TestCaptionRevision:
    """按修正意见改写英文草稿。修正意见可以是整段中文。也可以是一句指示。"""

    def test_sends_both_draft_and_note_to_the_model(self, monkeypatch) -> None:
        """草稿要一起送出。只送指示的话模型不知道在改什么。"""
        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            captured["payload"] = kwargs["payload"]
            return {"choices": [{"message": {"content": "A revised caption."}}]}

        monkeypatch.setattr(local_model, "_request_json", fake_request)
        revised = local_model.revise_caption_with_model(
            "A woman by the window.",
            "加入对肤色的描述。",
            connections=_OneConnection(),
        )

        assert revised == "A revised caption."
        user_message = captured["payload"]["messages"][-1]["content"]
        assert "A woman by the window." in user_message
        assert "加入对肤色的描述。" in user_message

    def test_failure_raises_so_the_draft_is_not_overwritten(self, monkeypatch) -> None:
        """改写失败要抛错。前端靠它决定不动既有草稿。"""
        unavailable = local_model.LocalModelError(SERVICE_DOWN)

        def explode(*_args, **_kwargs):
            raise unavailable

        monkeypatch.setattr(local_model, "_request_json", explode)
        with pytest.raises(local_model.LocalModelError):
            local_model.revise_caption_with_model(
                "A woman.", "改一下", connections=_OneConnection()
            )

    def test_empty_result_is_an_error_not_an_empty_draft(self, monkeypatch) -> None:
        monkeypatch.setattr(
            local_model,
            "_request_json",
            lambda *_args, **_kwargs: {"choices": [{"message": {"content": "   "}}]},
        )
        with pytest.raises(local_model.LocalModelError):
            local_model.revise_caption_with_model(
                "A woman.", "改一下", connections=_OneConnection()
            )

    def test_no_connection_is_an_error(self) -> None:
        with pytest.raises(local_model.LocalModelError):
            local_model.revise_caption_with_model("A woman.", "改一下", connections=None)

    def test_endpoint_reports_failure_as_422(self, settings, monkeypatch) -> None:
        down = api.LocalModelError(SERVICE_DOWN)

        def explode(*_args, **_kwargs):
            raise down

        monkeypatch.setattr(api, "revise_caption_with_model", explode)
        with TestClient(create_app(settings)) as client:
            response = client.post(
                "/api/captions/revise",
                json={"caption": "A woman.", "instruction": "改一下"},
            )

        assert response.status_code == 422
        assert SERVICE_DOWN in response.json()["detail"]


class _OneConnection:
    def get_caption_assist(self):
        return None

    def list_connections(self):
        return [
            ModelConnection(
                connection_id="c1",
                label="local",
                provider="lmstudio",
                base_url="http://127.0.0.1:1234/v1",
                api_key="",
                model_name="qwen",
                supports_vision=True,
            )
        ]


SERVICE_DOWN = "服务不可用"


class TestThinkingModels:
    """思考型模型会把 max_tokens 花在内部推理上。"""

    def test_thinking_is_disabled_in_the_request(self, monkeypatch) -> None:
        """不关掉的话额度全被推理吃光。content 是空的。"""
        captured = {}

        def fake_request(_url, **kwargs):
            captured["payload"] = kwargs["payload"]
            return {"choices": [{"message": {"content": '{"caption":"x"}'}}]}

        monkeypatch.setattr(local_model, "_request_json", fake_request)
        local_model._external_vision_completion(  # noqa: SLF001
            connection=_vision_connection(),
            system_prompt="s",
            text_prompt="t",
            image_data_url="data:image/jpeg;base64,AA==",
            temperature=0.1,
            max_tokens=300,
        )

        assert captured["payload"]["enable_thinking"] is False
        assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is False

    def test_empty_content_cut_by_length_says_so(self, monkeypatch) -> None:
        """只回「没有返回可识别的 JSON」会让人去怀疑提示词或模型能力。"""
        monkeypatch.setattr(
            local_model,
            "_request_json",
            lambda *_args, **_kwargs: {
                "choices": [{"message": {"content": ""}, "finish_reason": "length"}]
            },
        )
        with pytest.raises(local_model.LocalModelError, match="内部推理"):
            local_model._external_vision_completion(  # noqa: SLF001  # noqa: SLF001
                connection=_vision_connection(),
                system_prompt="s",
                text_prompt="t",
                image_data_url="data:image/jpeg;base64,AA==",
                temperature=0.1,
                max_tokens=300,
            )


def _vision_connection() -> ModelConnection:
    return ModelConnection(
        connection_id="c1",
        label="local",
        provider="openai_compatible",
        base_url="http://127.0.0.1:1234/v1",
        api_key="",
        model_name="qwen",
        supports_vision=True,
    )


class TestNoJsonDiagnostics:
    """模型回了散文而不是 JSON 时。最常见的原因是它拒绝描述这张图。"""

    def test_refusal_text_is_carried_into_the_error(self) -> None:
        """看不到原文的人会一直去调提示词。而该做的是换一个模型。"""
        message = local_model._no_json_message(  # noqa: SLF001
            "I can't caption this image. If you have other photos, I'm glad to help."
        )
        assert "拒绝" not in message  # 不替模型下判断。把它说的话带出来就好
        assert "I can't caption this image" in message

    def test_empty_content_says_empty_not_unparseable(self) -> None:
        assert local_model._no_json_message("   ")  # noqa: SLF001 == "视觉模型没有返回任何内容"

    def test_long_output_is_trimmed(self) -> None:
        assert len(local_model._no_json_message("x" * 5000)) < 250  # noqa: SLF001
