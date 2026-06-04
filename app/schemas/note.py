from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = ""
    note_type: str = "general"
    tags: Optional[str] = None
    is_mistake: bool = False
    subject: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[str] = None
    is_mistake: Optional[bool] = None
    subject: Optional[str] = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    note_type: str
    tags: Optional[str]
    is_mistake: bool
    subject: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
