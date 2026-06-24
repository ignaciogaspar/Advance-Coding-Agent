# FastAPI — Testing and Error Handling

## Testing with TestClient

FastAPI provides `TestClient`, built on `httpx`, to test your app without running
a server. Install with `pip install httpx pytest`.

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()

@app.get("/")
async def read_main():
    return {"msg": "Hello World"}

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Hello World"}
```

Write test functions whose names start with `test_` (the pytest convention),
call the client with `.get()`, `.post(json=...)`, etc., and assert on
`response.status_code` and `response.json()`. Run the tests with `pytest`.

## Raising HTTP errors with HTTPException

To return an HTTP error response to the client, raise `HTTPException`:

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()
items = {"foo": "The Foo Wrestlers"}

@app.get("/items/{item_id}")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}
```

`HTTPException` takes a `status_code` and a `detail` (any JSON-serializable
value). You can add custom headers with the `headers` argument. FastAPI converts
the exception into a JSON response like `{"detail": "Item not found"}` with the
given status code.

## Custom exception handlers

Register a handler with `@app.exception_handler(MyException)` to convert custom
exceptions into responses. You can also override the default handlers for
`RequestValidationError` and `StarletteHTTPException`.

## Status codes

Use the `status_code` parameter of the path operation decorator to set the
default success status (e.g. `@app.post("/items/", status_code=201)`). The
`fastapi.status` module provides readable constants such as
`status.HTTP_201_CREATED` and `status.HTTP_404_NOT_FOUND`.
