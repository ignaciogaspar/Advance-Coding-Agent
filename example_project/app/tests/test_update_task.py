import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import TaskStatus

client = TestClient(app)

@pytest.fixture
def create_task():
    response = client.post("/tasks/", json={"title": "Test Task", "description": "Test Description"})
    return response.json()


def test_update_task_status(create_task):
    task_id = create_task['id']
    response = client.patch(f"/tasks/{task_id}", json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()['status'] == "in_progress"

    response = client.patch(f"/tasks/{task_id}", json={"status": "done"})
    assert response.status_code == 200
    assert response.json()['status'] == "done"


def test_update_nonexistent_task():
    response = client.patch("/tasks/999", json={"status": "done"})
    assert response.status_code == 404
    assert response.json()['detail'] == "Task not found"