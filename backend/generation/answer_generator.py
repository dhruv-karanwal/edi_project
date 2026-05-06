from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, UnidentifiedImageError

from config import get_settings
from llm.base_client import LLMClient
from llm.ollama_client import OllamaClient

class AnswerGenerator:
    """Generate answers via configured LLM provider while keeping RAG flow intact."""

    def __init__(self):
        self.settings = get_settings()
        self.llm_client, self.client_error = self._build_client()

    def _build_client(self) -> Tuple[Optional[LLMClient], Optional[str]]:
        provider = self.settings.llm_provider.lower()
        try:
            if provider == "gemini":
                from llm.gemini_client import GeminiClient
                return GeminiClient(), None
            if provider == "ollama":
                return OllamaClient(), None
            return None, f"Unsupported LLM_PROVIDER: {provider}"
        except Exception as exc:
            return None, str(exc)

    def generate_answer(
        self,
        question: str,
        evidence: List[Dict],
        classification: Dict
    ) -> str:
        """Generate answer from question and evidence."""

        if not self.llm_client:
            return (
                "I am unable to generate an answer right now because the LLM provider "
                f"is not available ({self.client_error}). Please try again shortly."
            )

        # Separate evidence by type
        text_evidence = [e for e in evidence if e['chunk_type'] == 'text']
        figure_evidence = [e for e in evidence if e['chunk_type'] == 'figure']
        figure_image_evidence = [
            e for e in figure_evidence
            if self._is_usable_image(e.get('image_path'))
        ]
        table_evidence = [e for e in evidence if e['chunk_type'] == 'table']
        equation_evidence = [e for e in evidence if e['chunk_type'] == 'equation']
        
        # Build structured context for prompt grounding.
        context_parts = []

        context_parts.append("=== Query Metadata ===")
        context_parts.append(f"Question Type: {classification.get('query_type', 'unknown')}")
        context_parts.append(f"Requires Visual Reasoning: {bool(classification.get('requires_visual'))}")

        # Add text context
        if text_evidence:
            context_parts.append("=== Text Context ===")
            for i, ev in enumerate(text_evidence[:5], 1):  # Limit to top 5
                context_parts.append(
                    f"[{i}] Page {ev['page_number']}: {ev['content'][:400]}"
                )
        
        # Add table context
        if table_evidence:
            context_parts.append("\n=== Tables ===")
            for i, ev in enumerate(table_evidence, 1):
                caption = ev.get('caption', 'No caption')
                context_parts.append(
                    f"[Table {i}] Page {ev['page_number']}: {caption}\n{ev['content'][:400]}"
                )

        # Add figure context so model can align visual references with figure numbers.
        if figure_evidence:
            context_parts.append("\n=== Figures ===")
            for i, ev in enumerate(figure_evidence[:5], 1):
                caption = ev.get('caption') or ev.get('content', '')
                context_parts.append(
                    f"[Figure Candidate {i}] Page {ev['page_number']}: {caption[:400]}"
                )
        
        # Add equation context
        if equation_evidence:
            context_parts.append("\n=== Equations ===")
            for i, ev in enumerate(equation_evidence, 1):
                context_parts.append(
                    f"[Equation {i}] Page {ev['page_number']}: {ev['content']}"
                )
        
        context_text = "\n\n".join(context_parts) if context_parts else "No evidence retrieved."

        use_visual = bool(figure_image_evidence and classification.get('requires_visual'))
        image_paths = self._collect_image_paths(figure_image_evidence) if use_visual else []

        query_prompt = self._build_query_prompt(question, use_visual, classification)

        try:
            return self.llm_client.generate_answer(
                query=query_prompt,
                context=context_text,
                images=image_paths,
            )
        except Exception as exc:
            print(f"Answer generation failed: {exc}")
            return (
                "I am unable to generate an answer right now due to an upstream LLM error. "
                "Please try again in a moment."
            )

    def _build_query_prompt(self, question: str, use_visual: bool, classification: Dict) -> str:
        visual_instruction = (
            "If figure images are attached, analyze axes, legends, labels, trends, and visual patterns "
            "before answering."
            if use_visual
            else "No figure images are attached for this query."
        )

        reference_instruction = ""
        if classification.get('figure_number'):
            reference_instruction = (
                f"The user explicitly asked about Figure {classification['figure_number']}. "
                f"Use only evidence that clearly refers to Figure {classification['figure_number']}. "
                "If exact reference evidence is missing, say that instead of substituting another figure."
            )
        elif classification.get('table_number'):
            reference_instruction = (
                f"The user explicitly asked about Table {classification['table_number']}. "
                f"Use only evidence that clearly refers to Table {classification['table_number']}. "
                "If exact reference evidence is missing, say that instead of substituting another table."
            )

        return (
            "You are a production research-paper RAG assistant. "
            "Use only retrieved evidence context. "
            "If evidence is insufficient, clearly say so. "
            "Cite page numbers in-line when making claims.\n\n"
            f"User Question: {question}\n"
            f"{visual_instruction}\n\n"
            f"{reference_instruction}\n\n"
            "Response requirements:\n"
            "1) Give a direct answer first.\n"
            "2) Add brief supporting rationale grounded in evidence.\n"
            "3) Mention uncertainty explicitly when evidence is partial."
        )

    def _collect_image_paths(self, figure_evidence: List[Dict]) -> List[str]:
        image_paths: List[str] = []
        for fig in figure_evidence[:3]:
            path = fig.get("image_path")
            if path and Path(path).exists():
                image_paths.append(path)
        return image_paths

    def _is_usable_image(self, image_path: Optional[str]) -> bool:
        if not image_path:
            return False

        path = Path(image_path)
        if not path.exists() or not path.is_file():
            return False

        try:
            with Image.open(path) as img:
                gray = img.convert("L")
                extrema = gray.getextrema()
                if not extrema:
                    return False

                _, max_px = extrema
                if max_px <= 8:
                    return False

                histogram = gray.histogram()
                total = sum(histogram) or 1
                dark_ratio = sum(histogram[:8]) / total

                return dark_ratio <= 0.985
        except (OSError, UnidentifiedImageError, ValueError):
            return False