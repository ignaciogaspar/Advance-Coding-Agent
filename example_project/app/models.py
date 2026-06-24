"""Modelos Pydantic de la To-Do API."""
from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    done: bool = False


class Task(TaskCreate):
    id: int
