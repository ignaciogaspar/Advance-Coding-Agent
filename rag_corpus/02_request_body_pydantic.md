# FastAPI — Request Body with Pydantic

When a client sends data to your API, it sends it as a **request body**. A
request body is data sent by the client to your API; a response body is the data
your API sends back. To declare a request body you use Pydantic models.

To send data you should use `POST` (most common), `PUT`, `DELETE` or `PATCH`.
Sending a body with a `GET` request has undefined behavior in the specs and is
discouraged.

## Import Pydantic's BaseModel and create the model

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
```

Use standard Python types for the attributes. When a model attribute has a
default value it is **not required**; otherwise it is required. Use `None` to make
it optional.

## Declare it as a parameter

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/items/")
async def create_item(item: Item):
    return item
```

With just that type declaration, FastAPI will:

* Read the body of the request as JSON.
* Convert the corresponding types if needed.
* Validate the data, returning a clear error indicating exactly where and what
  was incorrect if invalid.
* Give you the received data in the parameter `item`, with full editor support.
* Generate JSON Schema definitions for your model, included in the OpenAPI schema
  used by the automatic docs.

## Using the model and combining parameters

Inside the function you can access all the attributes of the model directly,
e.g. `item.price`. You can declare path parameters and request body at the same
time — FastAPI recognizes that parameters matching the path come from the path,
and parameters declared as Pydantic models come from the body. You can also
declare body, path, and query parameters all at once:

* If the parameter is declared in the path, it is a path parameter.
* If it is of a singular type (`int`, `float`, `str`, `bool`), it is a query
  parameter.
* If it is declared as a Pydantic model, it is the request body.

If you don't want to use Pydantic models you can also use `Body` parameters.
