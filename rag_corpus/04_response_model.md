# FastAPI — Response Model and Return Type

You can declare the type used for the response by annotating the path operation
function **return type**. You can use Pydantic models, lists, dicts, or scalar
values.

```python
@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item
```

FastAPI uses the return type to **validate** the returned data, add a JSON Schema
for the response in the OpenAPI path operation, and **serialize** the data to
JSON using Pydantic (written in Rust, so it is fast). Most importantly, it will
**limit and filter** the output data to what is defined in the return type, which
is particularly important for **security**.

## response_model parameter

Sometimes you want to return data that is not exactly what the type declares — for
example, return a dict or a database object but declare it as a Pydantic model.
In those cases use the path operation decorator parameter `response_model` instead
of (or in addition to) the return type:

```python
@app.post("/items/", response_model=Item)
async def create_item(item: Item):
    return item
```

`response_model` can be a Pydantic model or, e.g., `list[Item]`. If you declare
both a return type and a `response_model`, the `response_model` takes priority.
Use `response_model=None` to disable response model generation.

## Filtering sensitive output (security)

Never return plaintext passwords. Create an input model with the password and a
separate output model without it, and use the output model as the response:

```python
class UserIn(BaseModel):
    username: str
    password: str
    email: str

class UserOut(BaseModel):
    username: str
    email: str

@app.post("/user/", response_model=UserOut)
async def create_user(user: UserIn):
    return user  # FastAPI filters out 'password' because it's not in UserOut
```

FastAPI filters out all data not declared in the output model. You can also use
class inheritance: a base model `BaseUser`, a `UserIn(BaseUser)` with the extra
password field, annotate the function return type as `BaseUser`, and FastAPI will
filter the output to the base fields while editors and mypy stay happy.

## Encoding parameters

* `response_model_exclude_unset=True` — return only values explicitly set, omitting
  defaults.
* `response_model_exclude_defaults=True` and `response_model_exclude_none=True`.
* `response_model_include={...}` and `response_model_exclude={...}` take a set of
  attribute names to include or exclude.

Recap: use `response_model` to define response models and especially to ensure
private data is filtered out; use `response_model_exclude_unset` to return only
the values explicitly set.
