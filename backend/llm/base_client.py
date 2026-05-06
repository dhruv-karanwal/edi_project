from abc import ABC, abstractmethod
from typing import List, Optional


class LLMClient(ABC):
    """Provider-agnostic interface for answer generation."""

    @abstractmethod
    def generate_answer(
        self,
        query: str,
        context: str,
        images: Optional[List[str]] = None,
    ) -> str:
        """Generate an answer from query + retrieved context + optional images."""
