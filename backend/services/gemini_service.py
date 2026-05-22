import os
import time
from typing import List, Dict, Any, Optional
from PIL import Image
import google.generativeai as genai
from config import get_settings
from utils.logger import logger

settings = get_settings()

class GeminiService:
    """Manages Google Gemini API client setup, multimodal prompt reasoning, and conversation memory."""
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.configured = False
        self._setup()

    def _setup(self):
        """Configures the Google Generative AI client."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not configured in settings. Generative features will fail.")
            return
        try:
            genai.configure(api_key=self.api_key)
            self.configured = True
            logger.info("Successfully configured Google Generative AI client.")
        except Exception as e:
            logger.error(f"Failed to configure Gemini client: {e}")

    def generate_answer(
        self,
        question: str,
        evidence: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]],
        crop_image_paths: List[str] = None
    ) -> str:
        """
        Sends grounded context (text + images) to Gemini.
        Returns the generated response string.
        """
        if not self.configured:
            # Attempt setup again in case API key was updated at runtime
            self.api_key = get_settings().gemini_api_key
            self._setup()
            if not self.configured:
                return "Error: Gemini API is not configured. Please supply a valid GEMINI_API_KEY in settings or your .env file."

        # 1. Compile text context from RAG evidence
        context_blocks = []
        for idx, ev in enumerate(evidence):
            source_info = f"[Source {idx+1}] Type: {ev['chunk_type']}, Page: {ev['page_number']}"
            if ev.get("section_title"):
                source_info += f", Section: {ev['section_title']}"
            context_blocks.append(f"{source_info}\nContent:\n{ev['snippet']}")

        text_context = "\n\n---\n\n".join(context_blocks)

        # 2. Build system instructions
        system_instruction = (
            "You are a professional research assistant powered by a Document Intelligence engine.\n"
            "Your goal is to answer user queries using the provided text extracts and visual document figures.\n"
            "RULES:\n"
            "1. Only answer based on the provided sources and context. Do not invent details.\n"
            "2. If the context does not contain the answer, say that you cannot find the answer in the document.\n"
            "3. Refer directly to sources in your response (e.g. 'According to Figure 1 on page 5...' or 'As shown in Table 2...').\n"
            "4. Your answer must be complete, professional, and formatted in Markdown."
        )

        # 3. Build past conversational message structure
        contents_payload = []
        
        # Inject context history
        for msg in chat_history:
            role = "user" if msg["role"] == "user" else "model"
            contents_payload.append({
                "role": role,
                "parts": [msg["content"]]
            })

        # 4. Prepare active user query parts (including RAG text and visual cropping evidence)
        prompt_parts = []
        prompt_parts.append(
            f"DOCUMENT SNIPPETS CONTEXT:\n{text_context}\n\n"
            f"USER QUERY: {question}\n\n"
            f"Please answer the query using the text context and any attached cropped figures/tables."
        )

        # Append cropped images as visual tokens for the vision model
        loaded_images = []
        if crop_image_paths:
            for path in crop_image_paths:
                if os.path.exists(path):
                    try:
                        img = Image.open(path)
                        # Ensure RGB format for JPEGs / PNGs
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        loaded_images.append(img)
                        logger.info(f"Loaded visual grounding crop: {path}")
                    except Exception as img_err:
                        logger.error(f"Failed to load crop image {path}: {img_err}")

        # Add image components to the active prompt payload
        prompt_parts.extend(loaded_images)

        contents_payload.append({
            "role": "user",
            "parts": prompt_parts
        })

        # 5. Invoke Gemini generation with auto retry logic
        model_name = settings.gemini_model
        generation_config = {
            "temperature": settings.gemini_temperature,
            "max_output_tokens": settings.gemini_max_tokens,
        }

        max_retries = 3
        backoff_seconds = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"Invoking Gemini model: {model_name} (Attempt {attempt+1}/{max_retries})...")
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction
                )
                
                response = model.generate_content(
                    contents=contents_payload,
                    generation_config=generation_config
                )
                
                if response and response.text:
                    logger.info("Successfully received answer from Gemini.")
                    return response.text
                else:
                    raise RuntimeError("Gemini model returned empty response.")
                    
            except Exception as api_err:
                logger.warning(f"Gemini API invocation attempt {attempt+1} failed: {api_err}")
                if attempt == max_retries - 1:
                    logger.error("All Gemini API retry attempts failed.")
                    return f"Error: Gemini API failed to respond. Details: {api_err}"
                time.sleep(backoff_seconds)
                backoff_seconds *= 2  # Exponential backoff
