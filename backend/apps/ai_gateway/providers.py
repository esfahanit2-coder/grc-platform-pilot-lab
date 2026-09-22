import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from rest_framework.exceptions import ValidationError
from .models import AIProviderConfig


@dataclass
class AIResponse:
    text: str
    raw: dict


class BaseProvider:
    def __init__(self, config: AIProviderConfig):
        self.config = config

    def generate(self, messages, *, temperature=0.2, response_format=None):
        raise NotImplementedError

    def embed(self, texts):
        raise NotImplementedError

    def _secret(self):
        if not self.config.secret_env_var:
            return ""
        return os.getenv(self.config.secret_env_var, "")


class MockProvider(BaseProvider):
    def embed(self, texts):
        import hashlib
        result=[]
        for text in texts:
            digest=hashlib.sha256((text or "").encode("utf-8")).digest()
            values=[(b/127.5)-1.0 for b in digest[:16]]
            norm=sum(v*v for v in values) ** 0.5 or 1.0
            result.append([v/norm for v in values])
        return result

    def generate(self, messages, *, temperature=0.2, response_format=None):
        text = "Mock AI response: " + (messages[-1].get("content", "")[:500] if messages else "")
        return AIResponse(text=text, raw={"mock": True, "text": text})


class OpenAICompatibleProvider(BaseProvider):
    def embed(self, texts):
        base = self.config.base_url.rstrip("/")
        if not base:
            raise ValidationError("AI provider base_url is required.")
        url = base if base.endswith("/embeddings") else f"{base}/embeddings"
        model = self.config.configuration.get("embedding_model") or self.config.model_name
        payload = {"model": model, "input": texts}
        headers = {"Content-Type": "application/json"}
        secret = self._secret()
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.configuration.get("timeout", 60))) as response:
                data = json.loads(response.read().decode("utf-8"))
            ordered = sorted(data.get("data") or [], key=lambda row: row.get("index", 0))
            return [row["embedding"] for row in ordered]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise ValidationError("Embedding provider request failed.") from exc

    def generate(self, messages, *, temperature=0.2, response_format=None):
        base = self.config.base_url.rstrip("/")
        if not base:
            raise ValidationError("AI provider base_url is required.")
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        payload = {"model": self.config.model_name, "messages": messages, "temperature": temperature, "stream": False}
        if response_format:
            payload["response_format"] = response_format
        headers = {"Content-Type": "application/json"}
        secret = self._secret()
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.configuration.get("timeout", 60))) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValidationError("AI provider request failed.") from exc
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValidationError("AI provider returned an unexpected response shape.") from exc
        return AIResponse(text=text or "", raw=data)


class OllamaProvider(BaseProvider):
    def embed(self, texts):
        base = self.config.base_url.rstrip("/") or "http://ollama:11434"
        url = f"{base}/api/embed"
        model = self.config.configuration.get("embedding_model") or self.config.model_name
        payload = {"model": model, "input": texts}
        if self.config.configuration.get("embedding_dimensions"):
            payload["dimensions"] = int(self.config.configuration["embedding_dimensions"])
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.configuration.get("timeout", 120))) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("embeddings") or []
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValidationError("Ollama embedding request failed.") from exc

    def generate(self, messages, *, temperature=0.2, response_format=None):
        base = self.config.base_url.rstrip("/") or "http://ollama:11434"
        url = f"{base}/api/chat"
        payload = {"model": self.config.model_name, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.configuration.get("timeout", 120))) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValidationError("Ollama request failed.") from exc
        text = ((data.get("message") or {}).get("content") or "").strip()
        return AIResponse(text=text, raw=data)


def provider_for(config: AIProviderConfig):
    if config.provider_type == AIProviderConfig.ProviderType.MOCK:
        return MockProvider(config)
    if config.provider_type == AIProviderConfig.ProviderType.OLLAMA:
        return OllamaProvider(config)
    return OpenAICompatibleProvider(config)
