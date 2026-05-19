from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.note import Note
from app.services.xp_breakdown import sync_user_xp
from pydantic import BaseModel
from typing import Optional
from fastapi import Depends

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    note_type: str = "general"
    tags: Optional[str] = None
    is_mistake: bool = False
    subject: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
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
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[NoteResponse])
async def list_notes(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    search: str | None = None,
    note_type: str | None = None,
    subject: str | None = None,
    is_mistake: bool | None = None,
):
    q = select(Note).where(Note.user_id == current_user.id)
    if search:
        q = q.where(or_(Note.title.ilike(f"%{search}%"), Note.content.ilike(f"%{search}%")))
    if note_type:
        q = q.where(Note.note_type == note_type)
    if subject:
        q = q.where(Note.subject == subject)
    if is_mistake is not None:
        q = q.where(Note.is_mistake == is_mistake)
    result = await db.execute(q.order_by(Note.updated_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=NoteResponse, status_code=201)
async def create_note(data: NoteCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    note = Note(user_id=current_user.id, **data.model_dump())
    db.add(note)
    current_user.xp += 10
    await db.flush()
    await db.refresh(note)
    return note


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int, data: NoteUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(note, k, v)
    await db.flush()
    await db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.flush()
    await sync_user_xp(db, current_user)
