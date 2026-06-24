"""Router de tareas — endpoints CRUD sobre una 'base de datos' en memoria."""
from fastapi import APIRouter, HTTPException

from ..models import Task, TaskCreate

router = APIRouter(prefix="/tasks", tags=["tasks"])

# "Base de datos" en memoria.
_DB: dict[int, Task] = {}
_NEXT_ID = 1


@router.get("/", response_model=list[Task])
async def list_tasks():
    return list(_DB.values())


@router.post("/", response_model=Task, status_code=201)
async def create_task(payload: TaskCreate):
    global _NEXT_ID
    task = Task(id=_NEXT_ID, **payload.model_dump())
    _DB[_NEXT_ID] = task
    _NEXT_ID += 1
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int):
    if task_id not in _DB:
        raise HTTPException(status_code=404, detail="Task not found")
    return _DB[task_id]


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int):
    if task_id not in _DB:
        raise HTTPException(status_code=404, detail="Task not found")
    del _DB[task_id]
