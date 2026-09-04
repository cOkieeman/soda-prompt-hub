from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    pass


class ModelClientError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """统一模型配置"""
    id: str
    provider: Literal["lm_studio", "openai", "anthropic", "custom"]
    base_url: str
    model_name: str
    api_key: str = ""
    supports_vision: bool = False
    max_tokens: int = 4096
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        """从字典创建配置"""
        api_key_env = data.get("api_key_env", "")
        api_key = os.environ.get(api_key_env, "") if api_key_env else data.get("api_key", "")
        
        return cls(
            id=str(data["id"]),
            provider=str(data.get("provider", "custom")),
            base_url=str(data["base_url"]),
            model_name=str(data["model_name"]),
            api_key=api_key,
            supports_vision=bool(data.get("supports_vision", False)),
            max_tokens=int(data.get("max_tokens", 4096)),
        )
    
    @classmethod
    def lm_studio_default(cls, model_name: str = "", supports_vision: bool = False) -> ModelConfig:
        """创建默认的 LM Studio 配置（向后兼容）"""
        return cls(
            id="lm_studio_local",
            provider="lm_studio",
            base_url="http://127.0.0.1:1234/v1",
            model_name=model_name,
            supports_vision=supports_vision,
        )


class UnifiedModelClient:
    """统一的模型客户端，支持文本和视觉任务"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
    
    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.35,
        max_tokens: int | None = None,
        timeout: float = 90,
    ) -> str:
        """统一的文本聊天接口"""
        max_tokens = max_tokens or self.config.max_tokens
        
        if self.config.provider in ("openai", "anthropic", "custom"):
            return self._openai_compatible_chat(messages, temperature, max_tokens, timeout)
        elif self.config.provider == "lm_studio":
            return self._lm_studio_chat(messages, temperature, max_tokens, timeout)
        else:
            raise ModelClientError(f"不支持的 provider: {self.config.provider}")
    
    def vision_completion(
        self,
        image_data_url: str,
        text_prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int | None = None,
        timeout: float = 180,
    ) -> str:
        """统一的视觉聊天接口"""
        if not self.config.supports_vision:
            raise ModelClientError(f"模型 {self.config.id} 不支持视觉任务")
        
        max_tokens = max_tokens or self.config.max_tokens
        
        if self.config.provider in ("openai", "custom"):
            return self._openai_vision(image_data_url, text_prompt, system_prompt, temperature, max_tokens, timeout)
        elif self.config.provider == "lm_studio":
            return self._lm_studio_vision(image_data_url, text_prompt, system_prompt, temperature, max_tokens, timeout)
        elif self.config.provider == "anthropic":
            return self._anthropic_vision(image_data_url, text_prompt, system_prompt, temperature, max_tokens, timeout)
        else:
            raise ModelClientError(f"不支持的视觉 provider: {self.config.provider}")
    
    def _openai_compatible_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        """OpenAI 兼容的文本聊天"""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        response = self._request(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            payload,
            headers,
            timeout,
        )
        
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise ModelClientError("模型返回格式错误") from error
    
    def _lm_studio_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        """LM Studio 文本聊天（使用 OpenAI 兼容端点）"""
        return self._openai_compatible_chat(messages, temperature, max_tokens, timeout)
    
    def _openai_vision(
        self,
        image_data_url: str,
        text_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        """OpenAI Vision API 格式"""
        messages: list[dict[str, Any]] = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url}
                },
                {"type": "text", "text": text_prompt}
            ]
        })
        
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        response = self._request(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            payload,
            headers,
            timeout,
        )
        
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise ModelClientError("模型返回格式错误") from error
    
    def _lm_studio_vision(
        self,
        image_data_url: str,
        text_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        """LM Studio 原生视觉格式"""
        server_root = self.config.base_url.rstrip("/").removesuffix("/v1")
        
        payload = {
            "model": self.config.model_name,
            "system_prompt": system_prompt,
            "input": [
                {"type": "image", "data_url": image_data_url},
                {"type": "text", "content": text_prompt}
            ],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "reasoning": "off",
            "stream": False,
            "store": False,
        }
        
        response = self._request(f"{server_root}/api/v1/chat", payload, {}, timeout)
        
        try:
            content = "\n".join(
                str(item.get("content", ""))
                for item in response["output"]
                if isinstance(item, dict) and item.get("type") == "message"
            )
            return content
        except (KeyError, TypeError) as error:
            raise ModelClientError("LM Studio 返回格式错误") from error
    
    def _anthropic_vision(
        self,
        image_data_url: str,
        text_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        """Anthropic Claude Vision 格式"""
        if "base64," in image_data_url:
            media_type = "image/jpeg"
            if "image/png" in image_data_url:
                media_type = "image/png"
            elif "image/webp" in image_data_url:
                media_type = "image/webp"
            
            base64_data = image_data_url.split("base64,")[1]
        else:
            raise ModelClientError("Anthropic 需要 Base64 编码的图片")
        
        payload = {
            "model": self.config.model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data,
                            }
                        },
                        {
                            "type": "text",
                            "text": text_prompt
                        }
                    ]
                }
            ]
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }
        
        response = self._request(
            f"{self.config.base_url.rstrip('/')}/messages",
            payload,
            headers,
            timeout,
        )
        
        try:
            return str(response["content"][0]["text"])
        except (KeyError, IndexError, TypeError) as error:
            raise ModelClientError("Anthropic 返回格式错误") from error
    
    def _request(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> Any:
        """统一的 HTTP 请求"""
        headers = headers.copy()
        headers["Content-Type"] = "application/json"
        
        data = json.dumps(payload).encode()
        request = Request(url, data=data, method="POST", headers=headers)
        
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()[:800]
            try:
                parsed_detail = json.loads(detail)
                detail = str(parsed_detail.get("error", {}).get("message") or detail)
            except (AttributeError, json.JSONDecodeError):
                pass
            message = f"模型服务返回 HTTP {error.code}"
            if detail:
                message += f"：{detail}"
            raise ModelClientError(message) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ModelClientError(f"无法连接模型服务：{error}") from error


def load_model_configs(config_path: Path) -> dict[str, ModelConfig]:
    """从配置文件加载模型配置"""
    if not config_path.exists():
        return {}
    
    try:
        with config_path.open() as f:
            data = json.load(f)
        
        configs = {}
        for model_data in data.get("models", []):
            config = ModelConfig.from_dict(model_data)
            configs[config.id] = config
        
        return configs
    except (OSError, json.JSONDecodeError, KeyError) as error:
        raise ModelClientError(f"无法加载模型配置：{error}") from error
