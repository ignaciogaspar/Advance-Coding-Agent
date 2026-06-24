# FastAPI — Dependency Injection

FastAPI has a powerful but intuitive **Dependency Injection** system. Dependency
Injection means your code (your path operation functions) can declare things it
requires to work, and FastAPI takes care of providing ("injecting") them. It is
useful to share logic, share database connections, and enforce security,
authentication, and role requirements — all while minimizing code repetition.

## Create a dependency ("dependable")

A dependency is just a function that can take the same parameters a path
operation function can take:

```python
from typing import Annotated
from fastapi import Depends, FastAPI

app = FastAPI()

async def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}

@app.get("/items/")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    return commons
```

## Import and declare Depends

Use `Depends` with a parameter, the same way you use `Body`, `Query`, etc. You
give `Depends` a single argument that must be something callable. You do **not**
call it yourself (no parentheses) — you pass it as a parameter. When a request
arrives, FastAPI calls your dependency with the correct parameters, gets the
result, and assigns it to the parameter in your path operation function.

## Share Annotated dependencies

Because `Annotated` is used, you can store the annotated value in a variable and
reuse it in multiple places, preserving type information:

```python
CommonsDep = Annotated[dict, Depends(common_parameters)]

@app.get("/items/")
async def read_items(commons: CommonsDep):
    return commons
```

This is especially useful in large code bases where the same dependencies are
used over and over.

## async or not

Dependencies can be `async def` or normal `def`, and you can mix them freely with
async or non-async path operation functions — FastAPI knows what to do.

## Hierarchical dependencies and security

Dependencies can depend on other dependencies, forming a hierarchical tree that
FastAPI solves for you. This lets you add different permission requirements per
endpoint, for example `current_user -> active_user -> admin_user`, and attach the
right dependency to each path operation to enforce authentication and roles.
All dependency requirements and validations are integrated into the OpenAPI
schema and shown in the interactive docs.
