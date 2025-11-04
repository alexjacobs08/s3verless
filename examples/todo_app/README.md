# Todo App Example

A simple todo list application demonstrating basic S3verless features.

## Features

- Create, read, update, and delete tasks
- Task status tracking (Todo, In Progress, Done)
- Priority levels
- Due dates
- Auto-generated REST API
- Admin interface

## Setup

1. Install dependencies:
```bash
# Using uv (recommended)
uv pip install s3verless uvicorn

# Or using pip
pip install s3verless uvicorn
```

2. Set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
export AWS_BUCKET_NAME=todo-app-bucket
export SECRET_KEY=your-secret-key
```

Or create a `.env` file:
```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET_NAME=todo-app-bucket
SECRET_KEY=your-secret-key
```

3. **Important**: Start LocalStack OR configure AWS credentials:

```bash
# Option A: Use LocalStack for local development (recommended)
docker run -d -p 4566:4566 localstack/localstack
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# Option B: Use real AWS (create .env file with your credentials)
```

4. Run the application:
```bash
python main.py
```

Or with uvicorn:
```bash
uvicorn main:app --reload
```

**Note**: If you see "Error loading data" in the admin interface, make sure LocalStack is running or your AWS credentials are configured correctly.

## API Endpoints

Once running, visit http://localhost:8000/docs for the interactive API documentation.

### Available Endpoints

- `GET /api/tasks/` - List all tasks
- `POST /api/tasks/` - Create a new task
- `GET /api/tasks/{id}` - Get a specific task
- `PUT /api/tasks/{id}` - Update a task
- `DELETE /api/tasks/{id}` - Delete a task
- `GET /api/tasks/search/?q=query` - Search tasks
- `GET /admin` - Admin interface

## Example Usage

### Create a task
```bash
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Buy groceries",
    "description": "Milk, eggs, bread",
    "status": "todo",
    "priority": 2
  }'
```

### List all tasks
```bash
curl http://localhost:8000/api/tasks/
```

### Update a task
```bash
curl -X PUT http://localhost:8000/api/tasks/{task_id} \
  -H "Content-Type: application/json" \
  -d '{
    "status": "done",
    "completed_at": "2024-01-15T10:30:00"
  }'
```

### Search tasks
```bash
curl "http://localhost:8000/api/tasks/search/?q=groceries"
```

## Admin Interface

Visit http://localhost:8000/admin to access the admin interface for managing tasks.

## LocalStack (Local Development)

For local testing without AWS:

```bash
# Start LocalStack
localstack start

# Update environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

