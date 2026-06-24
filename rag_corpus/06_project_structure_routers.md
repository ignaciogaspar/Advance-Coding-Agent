# FastAPI — Bigger Applications, Routers and Project Structure

For larger applications, split your code into multiple files using `APIRouter`.
An `APIRouter` works like a mini `FastAPI` class: it supports the same path
operation decorators (`@router.get`, `@router.post`, etc.).

## A typical project structure

```
.
├── app
│   ├── __init__.py
│   ├── main.py          # creates the FastAPI() app and includes routers
│   ├── dependencies.py  # shared dependencies
│   └── routers
│       ├── __init__.py
│       ├── items.py     # APIRouter for /items
│       └── users.py     # APIRouter for /users
```

## Define a router

```python
# app/routers/items.py
from fastapi import APIRouter

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
async def read_items():
    return [{"name": "Portal Gun"}, {"name": "Plumbus"}]

@router.get("/{item_id}")
async def read_item(item_id: str):
    return {"item_id": item_id}
```

`prefix` adds a path prefix to every route in the router, and `tags` group the
routes in the docs. You can also pass `dependencies=[Depends(...)]` to apply a
dependency to every route in the router.

## Include the router in the app

```python
# app/main.py
from fastapi import FastAPI
from .routers import items, users

app = FastAPI()
app.include_router(users.router)
app.include_router(items.router)

@app.get("/")
async def root():
    return {"message": "Hello Bigger Applications"}
```

`app.include_router(items.router)` adds all the routes from that router to the
main app. You can also include a router with an extra prefix, tags, dependencies
and responses, for example
`app.include_router(items.router, prefix="/api/v1", dependencies=[Depends(get_token_header)])`.

## Conventions and best practices

* Keep one `APIRouter` per resource (items, users, orders).
* Put shared dependencies in `dependencies.py`.
* Use `tags` consistently so the generated docs are well organized.
* Pin FastAPI and Pydantic versions in `requirements.txt`.
* Run with `uvicorn app.main:app --reload` in development, or `fastapi dev`.
* Add a `tests/` folder with `pytest` and `TestClient`.
