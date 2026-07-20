"""Modelos Pydantic de la To-Do API."""
from pydantic import BaseModel
from enum import Enum


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    done: bool = False


class Task(TaskCreate):
    id: int
    status: TaskStatus = TaskStatus.pending
