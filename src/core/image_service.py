from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field

import httpx

from src.app.settings import Settings


@dataclass(slots=True)
class ImageService:
    settings: Settings
    openrouter_client: httpx.AsyncClient
    _translation_cache: dict[str, str] = field(default_factory=dict)

    @property
    def provider_name(self) -> str:
        return (self.settings.image_backend_provider or "openrouter").strip().lower()

    @property
    def provider_model_name(self) -> str:
        provider = self.provider_name
        if provider == "openrouter":
            return self.settings.openrouter_image_model
        if provider == "openai":
            return self.settings.openai_image_model
        if provider == "modelslab":
            return self.settings.modelslab_model_id
        if provider == "together":
            return self.settings.tog_image_model
        return ""

    def analytics_context(self) -> tuple[str, str]:
        return self.provider_name, self.provider_model_name

    async def generate_image(self, prompt: str) -> bytes:
        provider = self.provider_name
        if provider == "openai":
            return await self._openai_generate_image(prompt, model_override=self.settings.openai_image_model)
        if provider == "openrouter":
            return await self._openrouter_generate_image(prompt, self.settings.openrouter_image_model)
        if provider == "modelslab":
            return await self._modelslab_generate_image(prompt)
        if provider == "together":
            return await self._together_generate_image(prompt, model=self.settings.tog_image_model)
        raise RuntimeError(f"Unknown IMAGE_BACKEND_PROVIDER={provider}")

    async def _translate_to_english(self, text: str) -> str:
        if self.settings.prompt_translation_debug:
            logging.info(
                "[translate][start] len=%s OPENAI_API_KEY=%s model=%s",
                len(text or ""),
                "SET" if self.settings.openai_api_key else "MISSING",
                self.settings.translation_model,
            )

        key = text.strip()
        if not key:
            return text
        if key in self._translation_cache:
            return self._translation_cache[key]
        if not self.settings.openai_api_key:
            if self.settings.prompt_translation_debug:
                logging.info("[translate][skip] OPENAI_API_KEY missing -> returning original")
            return text

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        system = (
            "You are a translation engine. Translate the user's text to natural English.\n"
            "Rules:\n"
            "- Return ONLY the translated text, no quotes, no explanations.\n"
            "- Preserve formatting, line breaks, punctuation.\n"
            "- Do NOT translate code, model IDs, LoRA names, URLs, tokens, weights like (word:1.2).\n"
            "- Keep proper nouns as-is.\n"
        )
        payload = {
            "model": self.settings.translation_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            logging.warning(
                "Translation failed HTTP %s: %s",
                response.status_code,
                (response.text or "")[:300],
            )
            return text

        data = response.json()
        out = (data["choices"][0]["message"]["content"] or "").strip()
        if out:
            self._translation_cache[key] = out
            return out
        return text

    async def _maybe_translate_prompt(self, provider: str, prompt: str) -> str:
        if self.settings.prompt_translation_debug:
            logging.info(
                "[translate][enter] provider=%s enabled=%s target=%s for=%s",
                provider,
                self.settings.prompt_translation_enabled,
                self.settings.prompt_translation_target_lang,
                self.settings.prompt_translation_for,
            )

        if not self.settings.prompt_translation_enabled:
            return prompt

        normalized_provider = provider.strip().lower()
        if normalized_provider not in self.settings.prompt_translation_for:
            return prompt
        if self.settings.prompt_translation_target_lang.lower() != "en":
            return prompt

        translated = await self._translate_to_english(prompt)
        if self.settings.prompt_translation_debug:
            original = (prompt or "").strip()
            result = (translated or "").strip()
            logging.info(
                "\n========== TRANSLATION DEBUG ==========\n"
                "provider=%s\n"
                "RU:\n%s\n"
                "EN:\n%s\n"
                "same=%s\n"
                "======================================",
                normalized_provider,
                original[:1200],
                result[:1200],
                str(original == result),
            )
        return translated

    async def _openai_generate_image(self, prompt: str, model_override: str | None = None) -> bytes:
        if not self.settings.openai_api_key:
            raise RuntimeError("Missing env OPENAI_API_KEY")

        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": (model_override or self.settings.openai_image_model).strip(),
            "prompt": prompt,
            "size": self.settings.openai_image_size,
            "n": 1,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            body_preview = (response.text or "")[:400]
            raise RuntimeError(f"OpenAI Images HTTP {response.status_code}: {body_preview}")

        data = response.json()
        return base64.b64decode(data["data"][0]["b64_json"])

    async def _modelslab_generate_image(self, prompt: str) -> bytes:
        if not self.settings.modelslab_api_key:
            raise RuntimeError("Missing MODELSLAB_API_KEY")
        if not self.settings.modelslab_model_id:
            raise RuntimeError("Missing MODELSLAB_MODEL_ID")

        translated_prompt = await self._maybe_translate_prompt("modelslab", prompt)
        negative = await self._maybe_translate_prompt("modelslab", self.settings.modelslab_negative_prompt)
        payload = {
            "key": self.settings.modelslab_api_key,
            "prompt": translated_prompt,
            "model_id": self.settings.modelslab_model_id,
            "width": str(self.settings.modelslab_width),
            "height": str(self.settings.modelslab_height),
            "negative_prompt": negative,
            "num_inference_steps": str(self.settings.modelslab_steps),
            "scheduler": self.settings.modelslab_scheduler,
            "guidance_scale": str(self.settings.modelslab_guidance),
            "enhance_prompt": self.settings.modelslab_enhance_prompt,
        }
        if self.settings.modelslab_lora_model:
            payload["lora_model"] = self.settings.modelslab_lora_model

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post("https://modelslab.com/api/v6/images/text2img", json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"ModelsLab HTTP {response.status_code}: {(response.text or '')[:600]}")

        data = response.json()
        urls = data.get("output") or data.get("proxy_links") or []
        if urls:
            return await self._download_image_bytes(urls[0])

        future = data.get("future_links") or []
        if future:
            try:
                return await self._download_image_bytes(future[0])
            except Exception:
                pass

        status = (data.get("status") or "").lower()
        fetch_url = data.get("fetch_result")
        if status == "processing" and fetch_url:
            eta = data.get("eta") or 5
            for _ in range(12):
                await asyncio.sleep(int(eta))
                async with httpx.AsyncClient(timeout=180.0) as client:
                    follow_up = await client.post(fetch_url, json={"key": self.settings.modelslab_api_key})
                if follow_up.status_code >= 400:
                    raise RuntimeError(f"ModelsLab fetch HTTP {follow_up.status_code}: {(follow_up.text or '')[:400]}")
                next_data = follow_up.json()
                urls2 = next_data.get("output") or next_data.get("proxy_links") or []
                if urls2:
                    return await self._download_image_bytes(urls2[0])
                future2 = next_data.get("future_links") or []
                if future2:
                    try:
                        return await self._download_image_bytes(future2[0])
                    except Exception:
                        pass
                eta = next_data.get("eta") or eta
            raise RuntimeError(f"ModelsLab: timeout waiting for image. Last response: {str(next_data)[:800]}")

        raise RuntimeError(f"ModelsLab: no image urls in response: {str(data)[:800]}")

    async def _download_image_bytes(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            raise RuntimeError(f"Image download failed HTTP {response.status_code}: {url}")
        return response.content

    async def _together_generate_image(self, prompt: str, model: str | None = None) -> bytes:
        if not self.settings.tog_api_key:
            raise RuntimeError("Missing env TOG_API_KEY")

        base_url = (self.settings.tog_base_url or "https://api.together.xyz/v1").rstrip("/")
        url = f"{base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.settings.tog_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": (model or self.settings.tog_image_model).strip(),
            "prompt": prompt,
            "n": 1,
            "width": int(self.settings.tog_width),
            "height": int(self.settings.tog_height),
        }

        last_err: str | None = None
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=240.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code in (429, 503):
                        last_err = response.text[:800] if response.text else ""
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    if response.status_code >= 400:
                        raise RuntimeError(f"Together Images HTTP {response.status_code}: {response.text[:800]}")
                    data = response.json()
                    item = (data.get("data") or [{}])[0]
                    b64 = item.get("b64_json")
                    if b64:
                        return base64.b64decode(b64)
                    url_out = item.get("url")
                    if url_out:
                        image_response = await client.get(url_out)
                        if image_response.status_code >= 400:
                            response_preview = (image_response.text or "")[:200]
                            raise RuntimeError(
                                f"Failed to download image URL {url_out}: "
                                f"HTTP {image_response.status_code}: {response_preview}"
                            )
                        return image_response.content
                    raise RuntimeError(f"No b64_json or url in Together response: {json.dumps(data)[:900]}")
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {repr(exc)}"
                await asyncio.sleep(0.7 * attempt)

        raise RuntimeError(f"Together image generation failed after retries. Last error: {last_err}")

    async def _openrouter_generate_image(self, prompt: str, image_model: str) -> bytes:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }
        payload = {
            "model": image_model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "stream": False,
        }

        response = await self.openrouter_client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )

        if response.status_code >= 400:
            body_preview = (response.text or "")[:400]
            raise RuntimeError(f"OpenRouter Images HTTP {response.status_code}: {body_preview}")

        data = response.json()
        try:
            message = data["choices"][0]["message"]
            images = message.get("images") or []
            if not images:
                raise KeyError("message.images empty")
            data_url = images[0]["image_url"]["url"]
        except Exception:
            preview = json.dumps(data, ensure_ascii=False)[:600]
            raise RuntimeError(f"No images in OpenRouter response: {preview}")
        return self._data_url_to_bytes(data_url)

    @staticmethod
    def _data_url_to_bytes(data_url: str) -> bytes:
        if not data_url or not data_url.startswith("data:"):
            raise RuntimeError("OpenRouter returned non-data-url image")
        try:
            _, b64 = data_url.split(",", 1)
        except ValueError as exc:
            raise RuntimeError("Malformed data URL") from exc
        return base64.b64decode(b64)
