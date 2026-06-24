"""API de ejemplo en FastAPI — gestión de tareas (To-Do).

Este es el repositorio objetivo sobre el que opera el Coding Agent Avanzado.
Es intencionalmente pequeño pero realista: tiene modelos Pydantic, un router,
una "base de datos" en memoria y endpoints CRUD.
"""
from fastapi import FastAPI, HTTPException

from .models import Task, TaskCreate
from .routers import tasks

app = FastAPI(title="To-Do API", version="0.1.0")

app.include_router(tasks.router)


@app.get("/")
async def root():
    return {"message": "To-Do API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
