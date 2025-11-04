"""S3verless CLI tool."""

import asyncio
import importlib.util
import sys
from pathlib import Path

import click

from s3verless import S3verlessSettings
from s3verless.core.client import S3ClientManager
from s3verless.core.registry import get_all_metadata, get_all_models


@click.group()
def cli():
    """S3verless CLI - Manage your S3-backed applications."""
    pass


@cli.command()
@click.argument("app_name")
@click.option(
    "--template", default="basic", help="Template to use (basic, ecommerce, blog)"
)
def init(app_name, template):
    """Initialize a new S3verless project."""
    click.echo(f"Creating new S3verless project: {app_name}")

    # Create project directory
    project_dir = Path(app_name)
    project_dir.mkdir(exist_ok=True)

    # Create basic structure
    (project_dir / "models").mkdir(exist_ok=True)
    (project_dir / "api").mkdir(exist_ok=True)

    # Create .env.example
    env_content = f"""# S3verless Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET_NAME=your-bucket-name
AWS_URL=http://localhost:4566  # For LocalStack

# Auth Settings
SECRET_KEY=your-secret-key-change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App Settings
APP_NAME={app_name}
DEBUG=true
S3_BASE_PATH={app_name}/
"""

    (project_dir / ".env.example").write_text(env_content)

    # Create main.py
    main_content = '''"""Main application file."""

from s3verless import create_s3verless_app, S3verlessSettings

# Import your models here
from models import *

# Create the app
app = create_s3verless_app(
    title="{app_name} API",
    description="API powered by S3verless",
    model_packages=["models"],
    enable_admin=True,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''.format(app_name=app_name.replace("-", " ").title())

    (project_dir / "main.py").write_text(main_content)

    # Create sample model based on template
    if template == "ecommerce":
        model_content = '''"""E-commerce models."""

from s3verless import BaseS3Model
from pydantic import Field
from typing import Optional
from decimal import Decimal


class Product(BaseS3Model):
    """Product model."""
    _plural_name = "products"
    
    name: str = Field(..., min_length=1, max_length=200)
    description: str
    price: Decimal = Field(..., ge=0, decimal_places=2)
    stock: int = Field(0, ge=0)
    category: str
    image_url: str | None = None


class Customer(BaseS3Model):
    """Customer model."""
    _plural_name = "customers"
    
    name: str
    email: str
    phone: str | None = None
'''
    elif template == "blog":
        model_content = '''"""Blog models."""

from s3verless import BaseS3Model
from pydantic import Field
from typing import Optional, List
import uuid


class Author(BaseS3Model):
    """Author model."""
    _plural_name = "authors"
    
    name: str
    email: str
    bio: str | None = None


class Post(BaseS3Model):
    """Blog post model."""
    _plural_name = "posts"
    
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    author_id: uuid.UUID
    tags: List[str] = Field(default_factory=list)
    is_published: bool = False
'''
    else:
        model_content = '''"""Sample models."""

from s3verless import BaseS3Model
from pydantic import Field
from typing import Optional


class Item(BaseS3Model):
    """Sample item model."""
    _plural_name = "items"
    
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    value: float = Field(0.0)
    is_active: bool = True
'''

    (project_dir / "models" / "__init__.py").write_text(model_content)

    # Create requirements.txt
    requirements = """s3verless>=0.2.0
fastapi
uvicorn[standard]
python-dotenv
"""
    (project_dir / "requirements.txt").write_text(requirements)

    # Create README
    readme = f"""# {app_name}

A S3verless application that stores all data in Amazon S3.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and configure your AWS credentials:
   ```bash
   cp .env.example .env
   ```

3. Run the application:
   ```bash
   python main.py
   ```

4. Visit:
   - API: http://localhost:8000
   - Admin: http://localhost:8000/admin
   - Docs: http://localhost:8000/docs

## Development with LocalStack

1. Start LocalStack:
   ```bash
   docker run -d -p 4566:4566 localstack/localstack
   ```

2. Update `.env` to use LocalStack:
   ```
   AWS_URL=http://localhost:4566
   ```
"""
    (project_dir / "README.md").write_text(readme)

    click.echo(f"✅ Project created at: {project_dir}")
    click.echo("📁 Next steps:")
    click.echo(f"   cd {app_name}")
    click.echo("   pip install -r requirements.txt")
    click.echo("   cp .env.example .env")
    click.echo("   # Edit .env with your settings")
    click.echo("   python main.py")


@cli.command()
@click.argument("model_file")
def inspect(model_file):
    """Inspect models in a Python file."""
    click.echo(f"Inspecting models in: {model_file}")

    # Load the module
    spec = importlib.util.spec_from_file_location("models", model_file)
    if not spec or not spec.loader:
        click.echo("❌ Could not load file")
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules["models"] = module
    spec.loader.exec_module(module)

    # Get all models
    models = get_all_models()
    metadata = get_all_metadata()

    if not models:
        click.echo("No models found")
        return

    click.echo(f"\nFound {len(models)} model(s):\n")

    for name, model_class in models.items():
        meta = metadata.get(name)
        click.echo(f"📋 {name}")
        click.echo(f"   Plural: {meta.plural_name if meta else 'N/A'}")
        click.echo(f"   API: {meta.api_prefix if meta else 'N/A'}")
        click.echo("   Fields:")

        for field_name, field_info in model_class.model_fields.items():
            if not field_name.startswith("_"):
                required = field_info.is_required()
                field_type = (
                    field_info.annotation.__name__
                    if hasattr(field_info.annotation, "__name__")
                    else str(field_info.annotation)
                )
                click.echo(
                    f"     - {field_name}: {field_type} {'(required)' if required else '(optional)'}"
                )
        click.echo()


@cli.command()
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--prefix", default="", help="S3 prefix to list")
@click.option("--endpoint", help="S3 endpoint URL (for LocalStack)")
def list_data(bucket, prefix, endpoint):
    """List data stored in S3."""

    async def _list():
        settings = S3verlessSettings(aws_bucket_name=bucket, aws_url=endpoint)

        manager = S3ClientManager(
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region,
            endpoint_url=endpoint,
        )

        async with manager.get_async_client() as s3_client:
            response = await s3_client.list_objects_v2(
                Bucket=bucket, Prefix=prefix, MaxKeys=100
            )

            if "Contents" not in response:
                click.echo("No objects found")
                return

            click.echo(f"\nObjects in s3://{bucket}/{prefix}:\n")

            for obj in response["Contents"]:
                key = obj["Key"]
                size = obj["Size"]
                modified = obj["LastModified"]
                click.echo(f"  {key} ({size} bytes) - {modified}")

    asyncio.run(_list())


@cli.command()
@click.argument("model_name")
@click.option("--app", default="main.py", help="Application file")
def seed(model_name, app):
    """Seed data for a specific model."""
    click.echo(f"Seeding data for {model_name}...")

    # This would import the app and create sample data
    click.echo("🌱 Feature coming soon!")


@cli.command()
def version():
    """Show S3verless version."""
    from s3verless import __version__

    click.echo(f"S3verless version: {__version__}")


if __name__ == "__main__":
    cli()
