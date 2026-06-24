# FastAPI — First Steps

The simplest FastAPI file looks like this:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

Copy that to a file `main.py` and run the live server with `fastapi dev`. The
server starts at http://127.0.0.1:8000 and the interactive docs at
http://127.0.0.1:8000/docs (Swagger UI) and /redoc (ReDoc).

## OpenAPI

FastAPI generates a "schema" of your whole API using the OpenAPI standard. The
schema includes your API paths, the parameters they take, and the data
definitions ("schemas") of what is sent and received, using JSON Schema. You can
see the raw OpenAPI schema at http://127.0.0.1:8000/openapi.json. The OpenAPI
schema powers the two interactive documentation systems.

## Path operations

"Path" refers to the last part of the URL starting from the first `/`; it is also
called an "endpoint" or "route". "Operation" refers to an HTTP method:

* `POST`: to create data.
* `GET`: to read data.
* `PUT`: to update data.
* `DELETE`: to delete data.

Plus the more exotic `OPTIONS`, `HEAD`, `PATCH`, `TRACE`.

The decorator `@app.get("/")` tells FastAPI that the function right below handles
requests that go to the path `/` using a GET operation. This is the "path
operation decorator". You can also use `@app.post()`, `@app.put()`,
`@app.delete()`, etc.

## The path operation function

The function below the decorator is the "path operation function". FastAPI calls
it whenever it receives a matching request. It can be `async def` or a normal
`def` — FastAPI handles both correctly.

## Returning content

You can return a `dict`, `list`, singular values like `str` / `int`, or Pydantic
models. Many objects (including ORMs) are automatically converted to JSON.

## Recap

* Import `FastAPI`.
* Create an `app` instance.
* Write a path operation decorator like `@app.get("/")`.
* Define a path operation function, e.g. `def root(): ...`.
* Run the development server with `fastapi dev`.

`FastAPI` is a class that inherits directly from `Starlette`, so you can use all
Starlette functionality too.
