"""S3verless CLI tool."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Type

import click

from s3verless import S3verlessSettings
from s3verless.core.base import BaseS3Model
from s3verless.core.client import S3ClientManager
from s3verless.core.registry import (
    get_all_metadata,
    get_all_models,
    set_base_s3_path,
)


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

        manager = S3ClientManager(settings)

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


def _load_model_from_file(model_file: str, model_name: str) -> Type[BaseS3Model] | None:
    """Load a specific model class from a Python file."""
    spec = importlib.util.spec_from_file_location("user_models", model_file)
    if not spec or not spec.loader:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules["user_models"] = module
    spec.loader.exec_module(module)

    # Get all models from registry
    models = get_all_models()
    return models.get(model_name)


@cli.command()
@click.argument("model_name")
@click.option("--count", default=10, help="Number of records to generate")
@click.option("--file", "seed_file", type=click.Path(exists=True), help="JSON file with seed data")
@click.option("--clear", is_flag=True, help="Clear existing data before seeding")
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--endpoint", help="S3 endpoint URL (for LocalStack)")
@click.option("--app", "app_file", default="main.py", help="Application file containing models")
@click.option("--base-path", default="s3verless-data/", help="S3 base path for data")
@click.option("--locale", default="en_US", help="Locale for fake data generation")
@click.option("--output", type=click.Path(), help="Output generated data to JSON file (dry run)")
def seed(model_name, count, seed_file, clear, bucket, endpoint, app_file, base_path, locale, output):
    """Seed data for a specific model.

    Examples:
        # Generate 50 fake products
        s3verless seed Product --count 50 --bucket my-bucket

        # Load seed data from file
        s3verless seed Product --file seeds/products.json --bucket my-bucket

        # Clear and reseed
        s3verless seed Product --clear --count 20 --bucket my-bucket

        # Dry run - output to file without saving to S3
        s3verless seed Product --count 10 --output products.json --bucket my-bucket
    """
    from s3verless.seeding.generator import DataGenerator
    from s3verless.seeding.loader import SeedLoader

    async def _seed():
        # Set base S3 path
        set_base_s3_path(base_path)

        # Load the model
        model_class = _load_model_from_file(app_file, model_name)
        if not model_class:
            click.echo(f"❌ Model '{model_name}' not found in {app_file}")
            click.echo("Available models:")
            models = get_all_models()
            for name in models:
                click.echo(f"  - {name}")
            return

        click.echo(f"🌱 Seeding {model_name}...")

        # Generate or load data
        if seed_file:
            click.echo(f"📄 Loading data from {seed_file}")
            data = SeedLoader.load_from_file(seed_file)
            click.echo(f"   Found {len(data)} records")
        else:
            click.echo(f"🎲 Generating {count} fake records (locale: {locale})")
            generator = DataGenerator(locale=locale)
            data = generator.generate_instances(model_class, count)

        # Dry run - output to file
        if output:
            output_path = Path(output)
            # Convert data to JSON-serializable format
            serializable_data = []
            for item in data:
                serialized = {}
                for key, value in item.items():
                    if hasattr(value, 'isoformat'):
                        serialized[key] = value.isoformat()
                    elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        serialized[key] = str(value)
                    else:
                        serialized[key] = value
                serializable_data.append(serialized)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, default=str)
            click.echo(f"✅ Data written to {output_path}")
            click.echo(f"   (Dry run - no data saved to S3)")
            return

        # Connect to S3 and seed
        settings = S3verlessSettings(
            aws_bucket_name=bucket,
            aws_url=endpoint,
            s3_base_path=base_path,
        )
        manager = S3ClientManager(settings)

        async with manager.get_async_client() as s3_client:
            # Clear existing data if requested
            deleted = 0
            if clear:
                click.echo(f"🗑️  Clearing existing {model_name} data...")
                deleted = await SeedLoader.clear_model(s3_client, model_class, bucket)
                click.echo(f"   Deleted {deleted} records")

            # Seed the data
            click.echo(f"💾 Saving to S3 bucket '{bucket}'...")
            created = await SeedLoader.seed_model(s3_client, model_class, data, bucket)

            click.echo(f"\n✅ Seeding complete!")
            if deleted:
                click.echo(f"   🗑️  Deleted: {deleted} records")
            click.echo(f"   ✨ Created: {created} records")

    asyncio.run(_seed())


@cli.command()
def version():
    """Show S3verless version."""
    from s3verless import __version__

    click.echo(f"S3verless version: {__version__}")


# Migration commands group
@cli.group()
def migrate():
    """Database migration commands."""
    pass


@migrate.command("run")
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--endpoint", help="S3 endpoint URL (for LocalStack)")
@click.option("--dir", "migrations_dir", default="migrations", help="Migrations directory")
@click.option("--base-path", default="s3verless-data/", help="S3 base path for data")
def migrate_run(bucket, endpoint, migrations_dir, base_path):
    """Run pending migrations."""
    from s3verless.migrations import MigrationRunner

    async def _run():
        set_base_s3_path(base_path)

        settings = S3verlessSettings(
            aws_bucket_name=bucket,
            aws_url=endpoint,
            s3_base_path=base_path,
        )
        manager = S3ClientManager(settings)

        async with manager.get_async_client() as s3_client:
            runner = MigrationRunner(s3_client, bucket, Path(migrations_dir))
            results = await runner.run_pending()

            if not results:
                click.echo("✅ No pending migrations")
                return

            for r in results:
                click.echo(f"✓ {r['version']}: {r['description']}")

            click.echo(f"\n✅ Applied {len(results)} migration(s)")

    asyncio.run(_run())


@migrate.command("status")
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--endpoint", help="S3 endpoint URL (for LocalStack)")
@click.option("--dir", "migrations_dir", default="migrations", help="Migrations directory")
@click.option("--base-path", default="s3verless-data/", help="S3 base path for data")
def migrate_status(bucket, endpoint, migrations_dir, base_path):
    """Show migration status."""
    from s3verless.migrations import MigrationRunner

    async def _status():
        set_base_s3_path(base_path)

        settings = S3verlessSettings(
            aws_bucket_name=bucket,
            aws_url=endpoint,
            s3_base_path=base_path,
        )
        manager = S3ClientManager(settings)

        async with manager.get_async_client() as s3_client:
            runner = MigrationRunner(s3_client, bucket, Path(migrations_dir))
            applied = await runner.get_applied_migrations()
            pending = runner.get_pending_migrations()

            click.echo("\n📋 Migration Status:\n")

            if applied:
                click.echo("Applied:")
                for version in applied:
                    click.echo(f"  ✓ {version}")
            else:
                click.echo("Applied: (none)")

            if pending:
                click.echo("\nPending:")
                for migration in pending:
                    click.echo(f"  ○ {migration.version}: {migration.description}")
            else:
                click.echo("\nPending: (none)")

    asyncio.run(_status())


@migrate.command("rollback")
@click.argument("version")
@click.option("--bucket", required=True, help="S3 bucket name")
@click.option("--endpoint", help="S3 endpoint URL (for LocalStack)")
@click.option("--dir", "migrations_dir", default="migrations", help="Migrations directory")
@click.option("--base-path", default="s3verless-data/", help="S3 base path for data")
def migrate_rollback(version, bucket, endpoint, migrations_dir, base_path):
    """Rollback a specific migration."""
    from s3verless.migrations import MigrationRunner

    async def _rollback():
        set_base_s3_path(base_path)

        settings = S3verlessSettings(
            aws_bucket_name=bucket,
            aws_url=endpoint,
            s3_base_path=base_path,
        )
        manager = S3ClientManager(settings)

        async with manager.get_async_client() as s3_client:
            runner = MigrationRunner(s3_client, bucket, Path(migrations_dir))

            try:
                result = await runner.rollback(version)
                click.echo(f"✓ Rolled back {result['version']}: {result['description']}")
            except ValueError as e:
                click.echo(f"❌ {e}")

    asyncio.run(_rollback())


if __name__ == "__main__":
    cli()
