from pydantic import BaseModel, validator
from typing import Optional
from uuid import UUID

class QueryRequest(BaseModel):
    document_id: UUID
    question: str
    conversation_id: Optional[UUID] = None

    @validator("question")
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Question cannot be empty")
        return value.strip()