from __future__ import annotations

import base64
import hashlib
import io
import json
import mimetypes
import tempfile
import zipfile
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image, ImageOps

from prompt_hub.model_connections import (
    ModelConnectionError,
    ModelConnectionStore,
    validate_model_base_url,
)
from prompt_hub.studio_store import StudioError, write_json

MAX_RESPONSE_BYTES = 120 * 1024 * 1024
_PROVIDER_LOCK = RLock()
NOVELAI_CLIENT_HEADERS = {
    "User-Agent": "NAI-Launcher/1.0",
    "Origin": "https://novelai.net",
    "Referer": "https://novelai.net/",
}


MASK_BINARY_THRESHOLD = 155
MAX_PRECISE_REFERENCE_EDGE = 4096
NAI_CHARACTER_VERSION = 4
NAI_V45 = 4.5
NAI_V5 = 5


def novelai_capabilities(model: str) -> dict[str, Any]:
    base = model.removesuffix("-inpainting")
    version = (
        5
        if base.startswith("nai-diffusion-5")
        else 4.5
        if base.startswith("nai-diffusion-4-5")
        else 4
        if base.startswith("nai-diffusion-4")
        else 3
    )
    return {
        "version": version,
        "characters": 6 if version >= NAI_CHARACTER_VERSION else 0,
        "vibe": version < NAI_V5,
        "precise": version == NAI_V45,
        "params_version": 4 if version == NAI_V5 else 3,
        "medium": base == "nai-diffusion-5-full-medium",
        "inpainting_model": "nai-diffusion-4-5-curated-inpainting"
        if base == "nai-diffusion-5-curated"
        else base + "-inpainting",
    }


def read_response(request: Request, timeout: int = 600) -> bytes:
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                msg = "圖片服務回應超過大小限制"
                raise StudioError(msg)
            return raw
    except HTTPError as error:
        msg = f"圖片服務拒絕請求，HTTP {error.code}。請檢查模型、參數與憑證設定。"
        raise StudioError(msg) from error
    except (URLError, TimeoutError, OSError) as error:
        msg = "圖片服務連線中斷或逾時，請核對服務端記錄後處理此任務。"
        raise StudioError(msg) from error


def multipart(fields: dict[str, Any], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = f"PromptHub{uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    for name, path in files:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="reference{path.suffix}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode()
            + path.read_bytes()
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class ImageProviderStore:
    def __init__(self, root: Path) -> None:
        self.path = root / "private" / "image-providers.json"
        self._lock = _PROVIDER_LOCK

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"providers": [], "comfy_root": ""}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            msg = "圖片連線設定無法讀取，請檢查設定檔"
            raise StudioError(msg) from error

    def public(self) -> dict[str, Any]:
        value = self._read()
        return {
            "comfy_root": value.get("comfy_root", ""),
            "caption_worker": value.get("caption_worker", {}),
            "providers": [
                {key: item for key, item in provider.items() if key != "api_key"}
                | {"has_api_key": bool(provider.get("api_key"))}
                for provider in value.get("providers", [])
            ],
        }

    def get_provider(self, identifier: str) -> dict[str, Any] | None:
        """Read a private record for trusted services, including account refresh."""
        return next((p for p in self._read()["providers"] if p["id"] == identifier), None)

    def fill_caption_worker(self, defaults: dict[str, str]) -> None:
        with self._lock:
            config = self._read()
            worker = config.setdefault("caption_worker", {})
            for key, value in defaults.items():
                if not worker.get(key):
                    worker[key] = value
            write_json(self.path, config)

    def save(  # noqa: C901 - protocol validation and dispatch stay together
        self, values: dict[str, Any], *, novelai_account: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._lock:
            config = self._read()
            if "comfy_root" in values:
                config["comfy_root"] = str(values["comfy_root"])[:2000]
            if "caption_worker" in values:
                worker = values["caption_worker"]
                if not isinstance(worker, dict) or worker.get("device", "cpu") not in {
                    "cpu",
                    "cuda",
                }:
                    msg = "標注工作器設定格式有誤"
                    raise StudioError(msg)
                config["caption_worker"] = {
                    key: str(worker.get(key, ""))[:2000]
                    for key in (
                        "python",
                        "pixai_model",
                        "detector_model",
                        "embedder_model",
                        "device",
                    )
                }
            provider = values.get("provider")
            if provider is not None:
                if not isinstance(provider, dict) or not isinstance(
                    provider.get("capabilities", {}), dict
                ):
                    msg = "圖片連線設定格式有誤"
                    raise StudioError(msg)
                kind = provider.get("kind")
                parts = urlsplit(str(provider.get("base_url", "")).strip())
                if (
                    kind not in {"openai", "novelai"}
                    or parts.scheme not in {"http", "https"}
                    or not parts.hostname
                    or parts.username
                    or parts.query
                    or parts.fragment
                ):
                    msg = "請填寫有效的圖片服務地址和類型"
                    raise StudioError(msg)
                identifier = str(provider.get("id") or f"image-{uuid4().hex}")
                existing = next((p for p in config["providers"] if p["id"] == identifier), {})
                if (
                    existing.get("api_key")
                    and not provider.get("api_key")
                    and existing.get("base_url") != str(provider["base_url"]).strip().rstrip("/")
                ):
                    msg = "服務地址已變更，請填寫對應的 API Key"
                    raise StudioError(msg)
                entry = {
                    "id": identifier,
                    "kind": kind,
                    "label": str(provider.get("label") or kind)[:160],
                    "base_url": str(provider["base_url"]).strip().rstrip("/"),
                    "model": str(provider.get("model", ""))[:300],
                    "api_key": str(provider.get("api_key") or existing.get("api_key", "")),
                    "capabilities": {
                        "references": bool(
                            provider.get("capabilities", {}).get("references", True)
                        ),
                    },
                }
                if novelai_account is not None:
                    entry["novelai_account"] = novelai_account
                elif (
                    existing.get("novelai_account")
                    and entry["base_url"] == existing.get("base_url")
                    and entry["api_key"] == existing.get("api_key")
                ):
                    entry["novelai_account"] = existing["novelai_account"]
                config["providers"] = [p for p in config["providers"] if p["id"] != identifier] + [
                    entry
                ]
            write_json(self.path, config)
            result = self.public()
            if provider is not None:
                result["saved_provider_id"] = identifier
            return result

    def delete(self, identifier: str) -> dict[str, Any]:
        with self._lock:
            config = self._read()
            retained = [
                provider for provider in config["providers"] if provider["id"] != identifier
            ]
            if len(retained) == len(config["providers"]):
                msg = "圖片連線不存在"
                raise StudioError(msg)
            config["providers"] = retained
            write_json(self.path, config)
            return self.public()

    def discover_models(
        self, values: dict[str, Any], models: ModelConnectionStore
    ) -> list[dict[str, object]]:
        if values.get("kind") != "openai":
            msg = "此連線類型使用 NovelAI 模型選項"
            raise StudioError(msg)
        try:
            base_url = validate_model_base_url(str(values.get("base_url", "")))
            key = str(values.get("api_key") or "").strip()
            identifier = str(values.get("id", ""))
            if identifier and not key:
                with self._lock:
                    existing = next(
                        (
                            provider
                            for provider in self._read()["providers"]
                            if provider["id"] == identifier
                        ),
                        None,
                    )
                if existing is None:
                    msg = "圖片連線不存在"
                    raise StudioError(msg)
                if existing.get("api_key") and base_url != validate_model_base_url(
                    existing["base_url"]
                ):
                    msg = "服務地址已變更，請填寫對應的 API Key"
                    raise StudioError(msg)
                key = existing.get("api_key", "")
            return models.discover(base_url, key)
        except ModelConnectionError as error:
            raise StudioError(str(error)) from error

    def update_novelai_account(self, identifier: str, account: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            config = self._read()
            provider = next((p for p in config["providers"] if p["id"] == identifier), None)
            if not provider or provider["kind"] != "novelai":
                msg = "NovelAI 帳號連線不存在"
                raise StudioError(msg)
            provider["novelai_account"] = account
            write_json(self.path, config)
        return next(p for p in self.public()["providers"] if p["id"] == identifier)

    def disconnect_novelai(self, identifier: str) -> None:
        with self._lock:
            config = self._read()
            provider = next((p for p in config["providers"] if p["id"] == identifier), None)
            if not provider or provider["kind"] != "novelai":
                msg = "NovelAI 帳號連線不存在"
                raise StudioError(msg)
            provider["api_key"] = ""
            provider.pop("novelai_account", None)
            write_json(self.path, config)

    def require(self, identifier: str, kind: str) -> dict[str, Any]:
        provider = next((p for p in self._read()["providers"] if p["id"] == identifier), None)
        if provider is None or provider["kind"] != kind:
            msg = "請先在設定保存對應的圖片服務連線"
            raise StudioError(msg)
        if not provider["model"].strip():
            msg = "請在圖片連線中填寫可用的模型名稱"
            raise StudioError(msg)
        if (
            kind == "novelai"
            and provider["base_url"] in {"https://image.novelai.net", "https://api.novelai.net"}
            and (
                not provider.get("api_key")
                or provider.get("novelai_account", {}).get("authentication_status") == "invalid"
            )
        ):
            msg = "請先登入 NovelAI"
            raise StudioError(msg)
        return {**provider, "_cache_root": str(self.path.parent.parent / "studio" / "vibe-cache")}


def validate_provider_recipe(  # noqa: C901, PLR0912 - protocol validation and dispatch stay together
    provider: dict[str, Any], recipe: dict[str, Any], references: list[tuple[str, Path]]
) -> None:
    if references and not provider.get("capabilities", {}).get("references", True):
        msg = "這個連線尚未啟用參考圖能力"
        raise StudioError(msg)
    model = recipe.get("model") or provider["model"]
    if provider["kind"] == "openai":
        if model.startswith("gpt-image") and (recipe["width"], recipe["height"]) not in {
            (1024, 1024),
            (1024, 1536),
            (1536, 1024),
        }:
            msg = "GPT Image 圖片尺寸請選 1024×1024、1024×1536 或 1536×1024"
            raise StudioError(msg)
        if references and not any(role != "mask" for role, _ in references):
            msg = "遮罩需要搭配來源圖片"
            raise StudioError(msg)
        if sum(role == "mask" for role, _ in references) > 1:
            msg = "每個編輯任務使用一張遮罩"
            raise StudioError(msg)
    else:
        if recipe["width"] % 64 or recipe["height"] % 64:
            msg = "NovelAI 尺寸需要為 64 的倍數"
            raise StudioError(msg)
        mode = recipe["novelai_mode"]
        caps = novelai_capabilities(model)
        if mode in {"infill", "outpaint"}:
            sources = [path for role, path in references if role != "mask"]
            masks = [path for role, path in references if role == "mask"]
            if len(sources) != 1 or (mode == "infill" and len(masks) != 1):
                msg = "重繪需要一張來源圖與一張遮罩；擴圖需要一張來源圖"
                raise StudioError(msg)
        elif any(role == "mask" for role, _ in references):
            msg = "使用遮罩時，請選擇局部重繪模式"
            raise StudioError(msg)
        if references and mode == "img2img" and len(references) != 1:
            msg = "NovelAI 圖生圖需要一張來源圖"
            raise StudioError(msg)
        if references and mode in {"vibe", "precise", "mixed"} and not caps["vibe"]:
            msg = "目前的 NovelAI V5 未提供 Vibe／Precise，請選 V4.5 或圖生圖"
            raise StudioError(msg)
        if references and mode == "precise" and not caps["precise"]:
            msg = "Precise 參考需要 NovelAI V4.5 模型"
            raise StudioError(msg)


def png_bytes(path: Path, size: tuple[int, int] | None = None) -> bytes:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        if size is not None:
            image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="PNG")
    return output.getvalue()


def encode_vibe(provider: dict[str, Any], path: Path, model: str, information: float) -> str:
    raw = png_bytes(path)
    digest = hashlib.sha256(raw + model.encode() + str(information).encode()).hexdigest()
    cache = (
        Path(provider["_cache_root"]) / f"{digest}.json" if provider.get("_cache_root") else None
    )
    if cache and cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="studio-vibe-") as directory:
        image_path = Path(directory) / "reference.png"
        request_path = Path(directory) / "request.json"
        image_path.write_bytes(raw)
        request_path.write_text(
            json.dumps({"image": "image", "model": model, "information_extracted": information}),
            encoding="utf-8",
        )
        body, content_type = multipart({}, [("image", image_path), ("request", request_path)])
        encoded = base64.b64encode(
            read_response(
                Request(  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                    provider["base_url"].rstrip("/") + "/ai/encode-vibe",
                    data=body,
                    headers={
                        **NOVELAI_CLIENT_HEADERS,
                        "Authorization": f"Bearer {provider['api_key']}",
                        "Content-Type": content_type,
                    },
                    method="POST",
                )
            )
        ).decode()
    if cache:
        write_json(cache, encoded)
    return encoded


def openai_images(  # noqa: C901 - protocol validation and dispatch stay together
    provider: dict[str, Any],
    recipe: dict[str, Any],
    prompt: dict[str, Any],
    references: list[tuple[str, Path]],
) -> list[bytes]:
    validate_provider_recipe(provider, recipe, references)
    base = provider["base_url"]
    if not base.endswith("/v1"):
        base += "/v1"
    fields = {
        "model": recipe.get("model") or provider["model"],
        "prompt": prompt["positive"],
        "size": f"{recipe['width']}x{recipe['height']}",
        "n": 1,
    }
    if references:
        instructions = [
            f"Reference image {index + 1} supplies {role}."
            for index, (role, _) in enumerate(references)
            if role != "mask"
        ]
        fields["prompt"] += "\n\n" + " ".join(instructions)
    if prompt.get("negative"):
        fields["prompt"] += "\nAvoid: " + prompt["negative"]
    headers = {"Authorization": f"Bearer {provider['api_key']}"}
    if references:
        if not provider["capabilities"].get("references"):
            msg = "這個連線尚未啟用參考圖能力"
            raise StudioError(msg)
        images = [("image[]", path) for role, path in references if role != "mask"]
        masks = [("mask", path) for role, path in references if role == "mask"]
        body, content_type = multipart(fields, images + masks[:1])
        route = "/images/edits"
    else:
        body = json.dumps(fields).encode()
        content_type = "application/json"
        route = "/images/generations"
    headers["Content-Type"] = content_type
    raw = read_response(Request(base + route, data=body, headers=headers, method="POST"))  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
    recipe["_effective_request"] = {
        "route": route,
        "parameters": fields,
        "references": [
            {"role": role, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for role, path in references
        ],
    }
    try:
        data = json.loads(raw)["data"]
        images = []
        for item in data:
            if item.get("b64_json"):
                images.append(base64.b64decode(item["b64_json"], validate=True))
            elif item.get("url"):
                url = str(item["url"])
                if urlsplit(url).scheme not in {"http", "https"}:
                    msg = "圖片服務返回了無效的下載地址"
                    raise StudioError(msg)
                images.append(read_response(Request(url)))  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
        if not images:
            msg = "圖片服務沒有返回可讀取的圖片"
            raise StudioError(msg)
    except (ValueError, KeyError, TypeError) as error:
        msg = "圖片服務返回格式無效"
        raise StudioError(msg) from error
    return images


def novelai_images(  # noqa: C901, PLR0912, PLR0915 - protocol validation and dispatch stay together
    provider: dict[str, Any],
    recipe: dict[str, Any],
    prompt: dict[str, Any],
    references: list[tuple[str, Path]],
) -> list[bytes]:
    validate_provider_recipe(provider, recipe, references)
    model = recipe.get("model") or provider["model"]
    caps = novelai_capabilities(model)
    modern = caps["version"] >= NAI_CHARACTER_VERSION
    parameters: dict[str, Any] = {
        "params_version": caps["params_version"],
        "width": recipe["width"],
        "height": recipe["height"],
        "scale": recipe["cfg"],
        "steps": recipe["steps"],
        "n_samples": 1,
        "seed": prompt["seed"],
        "sampler": recipe.get("sampler", "k_euler_ancestral"),
        "noise_schedule": recipe.get("noise_schedule", "karras"),
        "uc": prompt["negative"],
        "qualityToggle": False,
        "sm": bool(recipe.get("smea")) if not modern else False,
        "sm_dyn": bool(recipe.get("smea_dyn")) if not modern else False,
        "dynamic_thresholding": bool(recipe.get("decrisp")) if not modern else False,
        "cfg_rescale": recipe.get("cfg_rescale", 0),
    }
    if modern:
        characters = [item for item in recipe.get("characters", []) if item.get("enabled", True)]
        use_coords = (
            bool(characters) and recipe.get("character_position_mode", "custom") == "custom"
        )
        parameters["use_coords"] = use_coords
        positive_chars = [
            {
                "char_caption": item.get("prompt", ""),
                "centers": [{"x": item.get("x", 0.5), "y": item.get("y", 0.5)}],
            }
            for item in characters
        ]
        negative_chars = [
            {**item, "char_caption": character.get("negative", "")}
            for item, character in zip(positive_chars, characters, strict=False)
        ]
        parameters["v4_prompt"] = {
            "caption": {"base_caption": prompt["positive"], "char_captions": positive_chars},
            "use_coords": use_coords,
            "use_order": True,
        }
        parameters["v4_negative_prompt"] = {
            "caption": {"base_caption": prompt["negative"], "char_captions": negative_chars},
            "legacy_uc": False,
        }
        parameters["characterPrompts"] = [
            {
                "prompt": item.get("prompt", ""),
                "uc": item.get("negative", ""),
                "center": {"x": item.get("x", 0.5), "y": item.get("y", 0.5)},
                "enabled": True,
            }
            for item in characters
        ]
    if caps["medium"]:
        parameters.update(steps=14, sampler="k_euler_ancestral", ucPresetId="heavy")
        parameters.pop("noise_schedule", None)
        parameters.pop("cfg_rescale", None)
    action = "generate"
    if references:
        mode = recipe["novelai_mode"]
        if mode in {"infill", "outpaint"}:
            source = next(path for role, path in references if role != "mask")
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                if mode == "outpaint":
                    margins = recipe.get("outpaint", {})
                    left, top, right, bottom = [
                        int(margins.get(k, 0)) for k in ("left", "top", "right", "bottom")
                    ]
                    if left + right + top + bottom == 0:
                        msg = "請至少設定一個擴圖邊距"
                        raise StudioError(msg)
                    size = (image.width + left + right, image.height + top + bottom)
                    if any(n % 64 or n > MAX_PRECISE_REFERENCE_EDGE for n in size):
                        msg = "擴圖後尺寸需要為 64 的倍數且不超過 4096"
                        raise StudioError(msg)
                    canvas = Image.new("RGB", size, "white")
                    canvas.paste(image, (left, top))
                    mask = Image.new("L", size, 255)
                    mask.paste(0, (left, top, left + image.width, top + image.height))
                    image = canvas
                else:
                    size = (recipe["width"], recipe["height"])
                    image = ImageOps.fit(image, size)
                    with Image.open(
                        next(path for role, path in references if role == "mask")
                    ) as opened_mask:
                        mask = ImageOps.fit(
                            opened_mask.convert("L"), size, method=Image.Resampling.NEAREST
                        )
                # Upstream samples the mask on the 8-pixel latent grid, then
                # expands it back to request resolution with nearest sampling.
                latent = mask.resize(
                    (max(1, size[0] // 8), max(1, size[1] // 8)), Image.Resampling.NEAREST
                ).point(lambda value: 255 if value > MASK_BINARY_THRESHOLD else 0)
                if not latent.getbbox():
                    msg = "遮罩為空，白色區域才會重繪"
                    raise StudioError(msg)
                mask = latent.resize(size, Image.Resampling.NEAREST).convert("RGB")
                source_buffer, mask_buffer = io.BytesIO(), io.BytesIO()
                image.save(source_buffer, "PNG")
                mask.save(mask_buffer, "PNG")
                parameters.update(
                    image=base64.b64encode(source_buffer.getvalue()).decode(),
                    mask=base64.b64encode(mask_buffer.getvalue()).decode(),
                    width=size[0],
                    height=size[1],
                    strength=recipe["strength"],
                    noise=recipe["noise"],
                    add_original_image=False,
                )
            action = "infill"
            model = caps["inpainting_model"]
        elif mode == "img2img":
            parameters.update(
                {
                    "image": base64.b64encode(
                        png_bytes(references[0][1], (recipe["width"], recipe["height"]))
                    ).decode(),
                    "strength": recipe["strength"],
                    "noise": recipe["noise"],
                }
            )
            action = "img2img"
        elif mode in {"vibe", "mixed"} and not (
            mode == "mixed"
            and any(
                option.get("mode") == "precise" for option in recipe.get("_reference_options", [])
            )
        ):
            parameters["reference_image_multiple"] = [
                encode_vibe(
                    provider,
                    path,
                    model,
                    recipe.get("_reference_options", [{}] * len(references))[index].get(
                        "information", recipe["reference_information"]
                    ),
                )
                if modern
                else base64.b64encode(png_bytes(path)).decode()
                for index, (_, path) in enumerate(references)
            ]
            parameters["reference_strength_multiple"] = [
                option.get("strength", recipe["reference_strength"])
                for option in recipe.get("_reference_options", [{}] * len(references))
            ]
            parameters["normalize_reference_strength_multiple"] = True
            if not modern:
                parameters["reference_information_extracted_multiple"] = [
                    recipe["reference_information"]
                ] * len(references)
        else:
            if not caps["precise"]:
                msg = "Precise 參考需要 NovelAI V4.5 模型"
                raise StudioError(msg)
            options = recipe.get("_reference_options", [{}] * len(references))
            if mode == "mixed":
                selected = [
                    (reference, option)
                    for reference, option in zip(references, options, strict=False)
                    if option.get("mode") == "precise"
                ]
                references = [reference for reference, _ in selected]
                options = [option for _, option in selected]
            parameters["director_reference_images"] = [
                base64.b64encode(png_bytes(path)).decode() for _, path in references
            ]
            parameters["director_reference_descriptions"] = [
                {
                    "caption": {
                        "base_caption": "style" if role == "style" else "character",
                        "char_captions": [],
                    },
                    "legacy_uc": False,
                }
                for role, _ in references
            ]
            parameters["director_reference_information_extracted"] = [1] * len(references)
            parameters["director_reference_strength_values"] = [
                option.get("strength", recipe["reference_strength"]) for option in options
            ]
            parameters["director_reference_secondary_strength_values"] = [
                1 - option.get("fidelity", recipe["reference_information"]) for option in options
            ]
            parameters["normalize_reference_strength_multiple"] = True
    payload = {
        "input": prompt["positive"],
        "model": model,
        "action": action,
        "parameters": parameters,
    }
    recipe["_effective_request"] = {
        **payload,
        "parameters": {
            key: value
            for key, value in parameters.items()
            if key not in {"image", "mask", "reference_image_multiple", "director_reference_images"}
        },
    }
    raw = read_response(
        Request(  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
            provider["base_url"].rstrip("/") + "/ai/generate-image",
            data=json.dumps(payload).encode(),
            headers={
                **NOVELAI_CLIENT_HEADERS,
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
    )
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_RESPONSE_BYTES:
                msg = "NovelAI 圖片封包解壓後超過大小限制"
                raise StudioError(msg)
            return [
                archive.read(item)
                for item in archive.infolist()
                if Path(item.filename).suffix.lower() in {".png", ".webp", ".jpg"}
                and item.file_size <= 50 * 1024 * 1024
            ]
    except zipfile.BadZipFile as error:
        msg = "NovelAI 返回的圖片封包無法讀取"
        raise StudioError(msg) from error
