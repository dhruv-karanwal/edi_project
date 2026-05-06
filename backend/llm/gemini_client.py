from pathlib import Path
from typing import List, Optional

import google.generativeai as genai
from PIL import Image

from config import get_settings
from llm.base_client import LLMClient


settings = get_settings()


class GeminiClient(LLMClient):
    """Client for Google Gemini API (text + multimodal)."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.timeout_seconds = settings.gemini_timeout_seconds

        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in your environment."
            )

        genai.configure(api_key=self.api_key)
        resolved_model = self._resolve_model_name(self.model_name)
        self.model = genai.GenerativeModel(resolved_model)

    def _resolve_model_name(self, configured_model: str) -> str:
        """Resolve a valid Gemini model name for generateContent.

        The free-tier model catalog can vary across regions/accounts. We first try the
        configured model, then fallback to the first Gemini model that supports
        generateContent.
        """
        try:
            models = list(genai.list_models())
        except Exception as exc:
            # If listing fails, keep configured value and let generate_content surface details.
            print(f"Warning: unable to list Gemini models ({exc}); using configured model")
            return configured_model

        # Model names from API look like "models/gemini-...".
        configured_variants = {
            configured_model,
            f"models/{configured_model}",
        }

        for model in models:
            methods = set(getattr(model, "supported_generation_methods", []) or [])
            if "generateContent" in methods and getattr(model, "name", "") in configured_variants:
                return model.name

        for model in models:
            methods = set(getattr(model, "supported_generation_methods", []) or [])
            name = getattr(model, "name", "")
            if "generateContent" in methods and "gemini" in name:
                print(f"Warning: configured model '{configured_model}' unavailable; using '{name}'")
                return name

        return configured_model

    def generate_answer(
        self,
        query: str,
        context: str,
        images: Optional[List[str]] = None,
    ) -> str:
        """Generate an answer using Gemini with optional figure images."""
        prompt = (
            f"{query}\n\n"
            "Retrieved evidence context (use this as the source of truth):\n"
            f"{context}"
        )

        parts = [prompt]
        for image_path in images or []:
            path = Path(image_path)
            if path.exists() and path.is_file():
                parts.append(Image.open(path))

        try:
            response = self.model.generate_content(
                parts,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
                request_options={"timeout": self.timeout_seconds},
            )

            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("Gemini returned an empty response")
            return text

        except Exception as exc:
            raise RuntimeError(f"Gemini generation failed: {exc}") from exc
