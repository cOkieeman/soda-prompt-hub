from __future__ import annotations

import hashlib
import io
from dataclasses import replace
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore, JobCancelledError
from prompt_hub.optional_model_download import download_file
from prompt_hub.optional_models import (
    OPTIONAL_MODELS,
    ModelFile,
    OptionalModelInstaller,
    self_check,
)
from prompt_hub.studio_providers import ImageProviderStore
from prompt_hub.visual_model import VisualModelError
from prompt_hub.web import INDEX_HTML


class Context:
    def __init__(self, cancel_at=None):
        self.updates = []
        self.cancel_at = cancel_at

    def update(self, current, total, message=""):
        self.updates.append((current, total, message))

    def raise_if_cancelled(self):
        if self.cancel_at and self.updates and self.updates[-1][0] >= self.cancel_at:
            raise JobCancelledError


class Response(io.BytesIO):
    def __init__(self, body, offset=0, *, wrong_range=False, full=False):
        super().__init__(body if full else body[offset:])
        self.status = 200 if not offset or full else 206
        self.headers = {
            "Content-Range": f"bytes {offset + int(wrong_range)}-{len(body) - 1}/{len(body)}"
        }

    def read(self, _size=-1):
        return super().read(3)


@pytest.fixture
def tiny_installer(settings, monkeypatch):
    bodies = {"model.onnx": b"tiny verified model", "selected_tags.csv": b"name,category\na,0\n"}
    model = replace(
        OPTIONAL_MODELS[0],
        files=tuple(
            ModelFile(name, len(body), hashlib.sha256(body).hexdigest())
            for name, body in bodies.items()
        ),
    )
    monkeypatch.setattr("prompt_hub.optional_models.OPTIONAL_MODELS", (model,))
    smoke = Mock()
    monkeypatch.setattr("prompt_hub.optional_models.self_check", smoke)
    requests = []

    def open_file(request, **_kwargs):
        requests.append(request)
        offset = int(request.get_header("Range")[6:-1])
        return Response(bodies[request.full_url.rsplit("/", 1)[-1]], offset)

    monkeypatch.setattr(
        "prompt_hub.optional_model_download.build_opener", lambda *_args: Mock(open=open_file)
    )
    store = BackgroundJobStore(settings.database_path)
    store.initialize()
    installer = OptionalModelInstaller(settings, store)
    return installer, model, requests, smoke


def test_model_catalog_is_pinned_and_complete():
    assert len(OPTIONAL_MODELS) == 6
    for model in OPTIONAL_MODELS:
        assert len(model.revision) == 40
        assert len(model.files) >= 1
        assert all(len(file.sha256) == 64 and file.size > 0 for file in model.files)


def test_status_and_page_do_not_start_downloads(tiny_installer, settings, monkeypatch):
    installer, _model, requests, _smoke = tiny_installer
    monkeypatch.setattr("prompt_hub.background_jobs.BackgroundJobRunner.start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        result = client.get("/api/optional-models")
        assert result.status_code == 200
        assert result.json()["models"][0]["state"] == "missing"
        assert 'id="optionalModelsDialog"' in client.get("/").text
    assert requests == []
    assert installer.store.list_jobs() == []
    assert not settings.models_root.exists()


def test_installer_verifies_both_files_before_ready_and_skips_repeated_network(tiny_installer):
    installer, model, requests, smoke = tiny_installer
    context = Context()
    installer.install(model, context)
    assert len(requests) == 2
    assert smoke.call_count == 1
    assert installer.model_status(model)["state"] == "ready"
    assert context.updates[-1][0] == context.updates[-1][1] == model.size
    installer.install(model, Context())
    assert len(requests) == 2
    (installer.root(model) / model.files[0].name).write_bytes(b"changed")
    assert installer.model_status(model)["state"] == "partial"


def test_self_test_failure_never_marks_ready(tiny_installer):
    installer, model, _requests, smoke = tiny_installer
    smoke.side_effect = VisualModelError("self-test failed")
    with pytest.raises(VisualModelError, match="self-test"):
        installer.install(model, Context())
    assert installer.model_status(model)["state"] == "unverified"
    assert not (installer.root(model) / "optional-install.json").exists()


def test_install_conflicting_file_is_not_overwritten(tiny_installer):
    installer, model, requests, _smoke = tiny_installer
    root = installer.root(model)
    root.mkdir(parents=True)
    target = root / "model.onnx"
    target.write_bytes(b"my existing model")
    with pytest.raises(VisualModelError, match="未覆盖"):
        installer.install(model, Context())
    assert target.read_bytes() == b"my existing model"
    assert requests == []


def test_cancel_keeps_partial_file_and_resumes_with_fixed_total(tiny_installer):
    installer, model, requests, _smoke = tiny_installer
    with pytest.raises(JobCancelledError):
        installer.install(model, Context(cancel_at=3))
    part = installer.root(model) / "model.onnx.part"
    assert part.stat().st_size == 3
    assert installer.model_status(model)["state"] != "ready"
    context = Context()
    installer.install(model, context)
    assert requests[1].get_header("Range") == "bytes=3-"
    assert all(total == model.size for _, total, _ in context.updates)
    assert installer.model_status(model)["state"] == "ready"


def test_disk_space_failure_makes_no_network_request(tiny_installer, monkeypatch):
    installer, model, requests, _smoke = tiny_installer
    monkeypatch.setattr("prompt_hub.optional_models.shutil.disk_usage", lambda _: Mock(free=0))
    with pytest.raises(VisualModelError, match="磁盘空间不足"):
        installer.install(model, Context())
    assert requests == []


def test_api_deduplicates_and_rejects_unknown_models(tiny_installer, settings, monkeypatch):
    installer, model, requests, _smoke = tiny_installer
    monkeypatch.setattr("prompt_hub.background_jobs._now", lambda: "2026-09-13T00:00:00+00:00")
    monkeypatch.setattr("prompt_hub.background_jobs.BackgroundJobRunner.start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        first = client.post(f"/api/optional-models/{model.id}/install")
        second = client.post(f"/api/optional-models/{model.id}/install")
        assert first.status_code == 202
        assert first.json()["job"]["job_id"] == second.json()["job"]["job_id"]
        assert client.post("/api/optional-models/unknown/install").status_code == 422
        job = first.json()["job"]
        assert client.post(f"/api/jobs/{job['job_id']}/cancel").json()["status"] == "canceled"
        retry = client.post(f"/api/optional-models/{model.id}/install").json()["job"]
        assert retry["status"] == "queued"
        assert retry["job_id"] != job["job_id"]
        assert client.get("/api/optional-models").json()["models"][0]["job"]["status"] == "queued"
    assert len(installer.store.list_jobs()) == 2
    assert requests == []


@pytest.mark.parametrize("linked_name", ["model.onnx", "model.onnx.part"])
def test_download_rejects_symlink_without_touching_target(tiny_installer, tmp_path, linked_name):
    installer, model, requests, _smoke = tiny_installer
    root = installer.root(model)
    root.mkdir(parents=True)
    external = tmp_path / "external"
    external.write_bytes(b"keep")
    (root / linked_name).symlink_to(external)
    with pytest.raises(VisualModelError, match="符号链接"):
        installer.install(model, Context())
    assert external.read_bytes() == b"keep"
    assert requests == []


@pytest.mark.parametrize("mode", ["bad-hash", "wrong-range", "oversized", "ignored-range"])
def test_download_integrity_and_range_guards(tmp_path, monkeypatch, mode):
    target = tmp_path / "model.onnx"
    part = tmp_path / "model.onnx.part"
    body = b"abcdef"
    if mode in {"wrong-range", "ignored-range"}:
        part.write_bytes(body[:3])
    response = Response(
        body + (b"overflow" if mode == "oversized" else b""),
        3 if part.exists() else 0,
        wrong_range=mode == "wrong-range",
        full=mode == "ignored-range",
    )
    monkeypatch.setattr(
        "prompt_hub.optional_model_download.build_opener",
        lambda *_: Mock(open=lambda *_a, **_k: response),
    )
    args = (
        target,
        "https://huggingface.co/test/file",
        len(body),
        "0" * 64 if mode == "bad-hash" else hashlib.sha256(body).hexdigest(),
        Context(),
    )
    if mode == "ignored-range":
        download_file(*args)
        assert target.read_bytes() == body
    else:
        with pytest.raises(VisualModelError):
            download_file(*args)
        assert not target.exists()


def test_installer_ui_has_opt_in_accessible_feedback_and_entry_points():
    for marker in (
        'id="optionalModelsDialog"',
        'aria-labelledby="optionalModelsTitle"',
        'data-open-optional-models=""',
        'data-open-optional-models="wd-swinv2-tagger-v3"',
        'role="status"',
        "prefers-reduced-motion",
        "/api/optional-models",
        "ensureLocalTagger",
        "refreshInstalledDatasetTaggers",
        "关闭此窗口\uff0c下载仍会继续",
    ):
        assert marker in INDEX_HTML


def test_ready_api_does_not_enqueue_another_download(tiny_installer, settings, monkeypatch):
    installer, model, requests, _ = tiny_installer
    installer.install(model, Context())
    monkeypatch.setattr("prompt_hub.background_jobs.BackgroundJobRunner.start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        response = client.post(f"/api/optional-models/{model.id}/install")
        assert response.json() == {"already_installed": True, "job": None}
    assert len(requests) == 2
    assert not installer.store.list_jobs()


@pytest.mark.parametrize("output", [np.zeros((1, 2)), np.zeros((1, 3)), np.full((1, 2), np.nan)])
def test_tagger_self_check_probes_output_shape_and_finiteness(monkeypatch, tmp_path, output):
    tagger = Mock()
    tagger.labels = [("a", 0), ("b", 0)]
    tagger.target_size = 4
    tagger.input_meta.name = "input"
    tagger.output_meta.name = "output"
    tagger.session.run.return_value = [output]
    factory = Mock(return_value=tagger)
    monkeypatch.setattr("prompt_hub.optional_models.WD14Tagger", factory)
    if output.shape == (1, 2) and np.isfinite(output).all():
        self_check(OPTIONAL_MODELS[0], tmp_path)
    else:
        with pytest.raises(VisualModelError, match="自检未通过"):
            self_check(OPTIONAL_MODELS[0], tmp_path)
    inputs = tagger.session.run.call_args.args[1]["input"]
    assert inputs.shape == (1, 4, 4, 3)
    assert inputs.dtype == np.float32
    assert not inputs.any()


def test_clip_self_check_uses_expected_model_contract(monkeypatch, tmp_path):
    validate = Mock()
    monkeypatch.setattr("prompt_hub.optional_models.validate_custom_visual_model", validate)
    self_check(OPTIONAL_MODELS[2], tmp_path)
    assert validate.call_args.kwargs["dimension"] == 512
    assert validate.call_args.kwargs["input_size"] == 224


def test_resume_disk_check_counts_only_remaining_bytes(tiny_installer, monkeypatch):
    installer, model, requests, _ = tiny_installer
    with pytest.raises(JobCancelledError):
        installer.install(model, Context(cancel_at=3))
    monkeypatch.setattr(
        "prompt_hub.optional_models.shutil.disk_usage",
        lambda _: Mock(free=model.size - 3 + 16 * 1024 * 1024),
    )
    installer.install(model, Context())
    assert requests[1].get_header("Range") == "bytes=3-"


def test_symlinked_install_directory_is_blocked(tiny_installer, tmp_path):
    installer, model, requests, _ = tiny_installer
    root = installer.root(model)
    root.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    root.symlink_to(outside, target_is_directory=True)
    assert installer.model_status(model)["state"] == "blocked"
    with pytest.raises(VisualModelError, match="符号链接"):
        installer.install(model, Context())
    assert not list(outside.iterdir())
    assert requests == []


def test_metadata_symlink_is_not_overwritten(tiny_installer, tmp_path):
    installer, model, requests, _ = tiny_installer
    root = installer.root(model)
    root.mkdir(parents=True)
    target = tmp_path / "keep.json"
    target.write_text("keep", encoding="utf-8")
    (root / "model-info.json").symlink_to(target)
    with pytest.raises(VisualModelError, match="符号链接"):
        installer.install(model, Context())
    assert target.read_text(encoding="utf-8") == "keep"
    assert requests == []


def test_first_run_choice_is_saved_per_library_without_downloads(
    tiny_installer, settings, monkeypatch
):
    installer, model, requests, _ = tiny_installer
    monkeypatch.setattr("prompt_hub.background_jobs.BackgroundJobRunner.start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/optional-models").json()["onboarding"] == {
            "completed": False,
            "selected": [],
        }
        assert (
            client.post(
                "/api/optional-models/onboarding", json={"selected": ["invalid"]}
            ).status_code
            == 422
        )
        assert client.post(
            "/api/optional-models/onboarding", json={"selected": [model.id, model.id]}
        ).json() == {"completed": True, "selected": [model.id]}
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/optional-models").json()["onboarding"]["completed"]
        assert (
            client.post("/api/optional-models/onboarding", json={"selected": []}).json()["selected"]
            == []
        )
    assert requests == []
    assert installer.store.list_jobs() == []


def test_caption_download_fills_defaults_and_preserves_existing_worker(tiny_installer, monkeypatch):
    installer, model, _, _ = tiny_installer
    monkeypatch.setattr("prompt_hub.optional_models.find_spec", lambda _: True)
    providers = ImageProviderStore(installer.settings.library_root)
    providers.save(
        {
            "caption_worker": {
                "python": "custom/python.exe",
                "device": "cuda",
                "detector_model": "custom/sam3",
            }
        }
    )
    caption_model = replace(model, caption_key="pixai_model")
    installer.install(caption_model, Context())
    worker = providers.public()["caption_worker"]
    assert worker["pixai_model"] == str(installer.root(model))
    assert worker["python"] == "custom/python.exe"
    assert worker["device"] == "cuda"
    assert worker["detector_model"] == "custom/sam3"


def test_caption_model_structure_is_checked_without_inference(tmp_path):
    model = next(model for model in OPTIONAL_MODELS if model.caption_key)
    (tmp_path / "config.json").write_text('{"model_type":"cls_vitdet"}', encoding="utf-8")
    self_check(model, tmp_path)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(VisualModelError):
        self_check(model, tmp_path)
