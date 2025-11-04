"""
Simple Todo App Example using S3verless

This example demonstrates:
- Basic model definition
- Auto-generated CRUD API
- Simple task management
"""

from datetime import datetime
from enum import Enum

from s3verless import BaseS3Model, create_s3verless_app
from s3verless.core.settings import S3verlessSettings


class TaskStatus(str, Enum):
    """Task status options."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Task(BaseS3Model):
    """A todo task."""

    _plural_name = "tasks"
    _api_prefix = "/api/tasks"

    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: int = 0
    due_date: datetime | None = None
    completed_at: datetime | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Complete documentation",
                "description": "Write comprehensive API documentation",
                "status": "todo",
                "priority": 1,
                "due_date": "2024-12-31T23:59:59",
            }
        }
    }


# Create the FastAPI app with sensible defaults
settings = S3verlessSettings(
    aws_bucket_name="todo-app-bucket", secret_key="dev-secret-key-change-in-production"
)
app = create_s3verless_app(
    settings=settings,
    title="Todo API",
    description="A simple todo list API powered by S3verless",
    version="1.0.0",
    enable_admin=True,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
