# To-Do API (proyecto de ejemplo)

API mínima en FastAPI usada como **repositorio objetivo** del Coding Agent
Avanzado. Implementa CRUD de tareas.

## Correr

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Docs interactivas en http://127.0.0.1:8000/docs

## Estructura

```
app/
  main.py            # crea la app FastAPI e incluye el router
  models.py          # modelos Pydantic (Task, TaskCreate)
  routers/tasks.py   # endpoints CRUD /tasks
```

## Endpoints

- `GET /` y `GET /health`
- `GET /tasks/` — lista tareas
- `POST /tasks/` — crea una tarea (201)
- `GET /tasks/{id}` — obtiene una tarea (404 si no existe)
- `DELETE /tasks/{id}` — borra una tarea (204)
