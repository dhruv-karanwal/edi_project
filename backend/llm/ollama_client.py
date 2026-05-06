import ollama
from typing import List, Dict, Optional
from config import get_settings
import base64
from llm.base_client import LLMClient

settings = get_settings()

class OllamaClient(LLMClient):
    """Client for interacting with Ollama LLM and VLM models."""
    
    def __init__(self):
        self.llm_model = settings.ollama_llm_model
        self.vlm_model = settings.ollama_vlm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.ollama_host = settings.ollama_host
        self.client = ollama.Client(host=self.ollama_host)
        
        # CPU-only local inference can be slow on laptops; keep a larger timeout.
        ollama._client.DEFAULT_TIMEOUT = 360.0
    
    def ensure_models_available(self):
        """Pull required models if not available."""
        try:
            models = self.client.list()
            model_names = {m['name'] for m in models.get('models', [])}
        except Exception as e:
            raise RuntimeError(
                f"Unable to connect to Ollama at {self.ollama_host}: {e}"
            ) from e

        if self.llm_model not in model_names:
            print(f"Pulling LLM model {self.llm_model}...")
            self.client.pull(self.llm_model)
            print(f"✓ LLM model {self.llm_model} ready")

        if self.vlm_model not in model_names:
            print(f"Pulling VLM model {self.vlm_model}...")
            self.client.pull(self.vlm_model)
            print(f"✓ VLM model {self.vlm_model} ready")
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text using Llama model."""
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    'role': 'system',
                    'content': system_prompt
                })
            
            messages.append({
                'role': 'user',
                'content': prompt
            })
            
            response = self.client.chat(
                model=self.llm_model,
                messages=messages,
                options={
                    'temperature': temperature or self.temperature,
                    'num_predict': max_tokens or self.max_tokens,
                }
            )

            return response['message']['content']
            
        except Exception as e:
            raise RuntimeError(f"Ollama text generation failed: {e}") from e
    
    def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate text using LLaVA vision model with image."""
        try:
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            messages = []
            
            if system_prompt:
                messages.append({
                    'role': 'system',
                    'content': system_prompt
                })
            
            messages.append({
                'role': 'user',
                'content': prompt,
                'images': [image_data]
            })
            
            response = self.client.chat(
                model=self.vlm_model,
                messages=messages,
                options={
                    'temperature': self.temperature,
                    'num_predict': self.max_tokens,
                }
            )
            
            return response['message']['content']
            
        except Exception as e:
            raise RuntimeError(f"Ollama image generation failed: {e}") from e

    def generate_answer(
        self,
        query: str,
        context: str,
        images: Optional[List[str]] = None,
    ) -> str:
        """Generate an answer from query + context + optional images."""
        prompt = (
            f"{query}\n\n"
            "Retrieved evidence context (use this as the source of truth):\n"
            f"{context}"
        )

        valid_images = [p for p in (images or []) if p]
        if valid_images:
            return self.generate_with_image(prompt, valid_images[0])
        return self.generate_text(prompt)
    
    def generate_with_context(
        self,
        question: str,
        context_chunks: List[Dict],
        image_paths: List[str] = None
    ) -> str:
        """Generate answer with retrieved context."""
        
        # Build context from text chunks
        context_parts = []
        for i, chunk in enumerate(context_chunks):
            context_parts.append(
                f"[{i+1}] Page {chunk['page_number']}, {chunk['chunk_type']}: {chunk['content'][:500]}"
            )
        
        context_text = "\n\n".join(context_parts)
        
        # If there are images, use vision model
        if image_paths:
            system_prompt = """You are a research paper analysis assistant. 
Answer questions based on the provided context and images from the paper.
Be precise and cite specific page numbers when making claims.
If you cannot answer based on the context, say so clearly."""
            
            prompt = f"""Question: {question}

Context from paper:
{context_text}

The images show figures/charts from the paper that are relevant to this question.

Provide a detailed answer based on the context and images. Include page references."""
            
            # Use first image for now (can be extended to handle multiple)
            return self.generate_with_image(prompt, image_paths[0], system_prompt)
        
        else:
            system_prompt = """You are a research paper analysis assistant.
Answer questions based ONLY on the provided context from the paper.
Be precise and cite specific page numbers when making claims.
If you cannot answer based on the context, say "I cannot find this information in the provided context." """
            
            prompt = f"""Question: {question}

Context from paper:
{context_text}

Provide a detailed answer based on the context. Include page references."""
            
            return self.generate_text(prompt, system_prompt)