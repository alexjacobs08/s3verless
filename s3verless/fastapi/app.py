"""S3verless FastAPI application factory."""

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from s3verless.core.base import BaseS3Model
from contextlib import asynccontextmanager

from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from s3verless.core.base import BaseS3Model
from s3verless.core.client import S3ClientManager
from s3verless.core.registry import get_all_metadata, set_base_s3_path
from s3verless.core.settings import S3verlessSettings
from s3verless.fastapi.admin import generate_admin_interface
from s3verless.fastapi.router_generator import generate_crud_router


def discover_models(package_path: str) -> list[type["BaseS3Model"]]:
    """Discover all BaseS3Model subclasses in a package."""
    models = []

    # Import the package
    try:
        package = importlib.import_module(package_path)
    except ImportError:
        return models

    # Get package directory
    if hasattr(package, "__path__"):
        package_dir = package.__path__[0]
    else:
        return models

    # Walk through all modules in the package
    for importer, modname, ispkg in pkgutil.walk_packages(
        [package_dir], f"{package_path}."
    ):
        try:
            module = importlib.import_module(modname)

            # Check all attributes in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Check if it's a class and subclass of BaseS3Model
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseS3Model)
                    and attr is not BaseS3Model
                ):
                    models.append(attr)

        except ImportError:
            continue

    return models


class S3verless:
    """Main S3verless application class."""

    def __init__(
        self,
        settings: S3verlessSettings | None = None,
        title: str = "S3verless API",
        description: str = "API powered by S3verless",
        version: str = "1.0.0",
        enable_admin: bool = True,
        model_packages: list[str] | None = None,
        auto_discover: bool = True,
    ):
        self.settings = settings or S3verlessSettings()
        self.title = title
        self.description = description
        self.version = version
        self.enable_admin = enable_admin
        self.model_packages = model_packages or []
        self.auto_discover = auto_discover
        self._app: FastAPI | None = None

        # Initialize S3 client manager
        self.s3_manager = S3ClientManager(self.settings)

        # Set global S3 manager in the client module
        from s3verless.core import client

        client.s3_manager = self.s3_manager

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Application lifespan manager."""
        # Startup
        print(f"🚀 Starting {self.title}...")

        # Set base S3 path
        base_path = self.settings.s3_base_path or "s3verless-data/"
        set_base_s3_path(base_path)
        print(f"📁 S3 base path: {base_path}")

        # Ensure bucket exists
        await self._ensure_bucket_exists()

        # Discover and register models
        if self.auto_discover:
            self._discover_and_register_models()

        # Create default admin user if configured
        await self._create_default_admin()

        # Generate routers for all registered models
        self._generate_routers(app)

        # Setup admin interface if enabled
        if self.enable_admin:
            self._setup_admin(app)

        print(f"✅ {self.title} started successfully!")

        yield

        # Shutdown
        print(f"👋 Shutting down {self.title}...")

    async def _ensure_bucket_exists(self):
        """Ensure the S3 bucket exists."""
        s3_client = self.s3_manager.get_sync_client()
        bucket_name = self.settings.aws_bucket_name

        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket '{bucket_name}' exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print(f"📦 Creating bucket '{bucket_name}'...")
                try:
                    s3_client.create_bucket(Bucket=bucket_name)
                    print(f"✅ Bucket '{bucket_name}' created")
                except ClientError as create_error:
                    print(f"❌ Failed to create bucket: {create_error}")
                    raise
            else:
                print(f"❌ Error checking bucket: {e}")
                raise

    async def _create_default_admin(self):
        """Create default admin user if configured."""
        if not self.settings.create_default_admin:
            return

        if not all(
            [
                self.settings.default_admin_username,
                self.settings.default_admin_password,
                self.settings.default_admin_email,
            ]
        ):
            return

        try:
            from s3verless.auth.models import S3User
            from s3verless.auth.service import S3AuthService
            from s3verless.core.service import S3DataService

            auth_service = S3AuthService(self.settings)

            async with self.s3_manager.get_async_client() as s3_client:
                # Check if admin already exists
                existing_admin = await auth_service.get_user_by_username(
                    s3_client, self.settings.default_admin_username
                )

                if not existing_admin:
                    # Create admin user
                    admin = await auth_service.create_user(
                        s3_client=s3_client,
                        username=self.settings.default_admin_username,
                        email=self.settings.default_admin_email,
                        password=self.settings.default_admin_password,
                        full_name="Default Admin",
                    )

                    # Set admin flag
                    admin.is_admin = True
                    user_service = S3DataService(S3User, self.settings.aws_bucket_name)
                    await user_service.update(s3_client, str(admin.id), admin)

                    print(
                        f"👤 Created default admin user: {self.settings.default_admin_username}"
                    )
                    print("⚠️  Change the password in production!")
                # Ensure existing user is admin
                elif not existing_admin.is_admin:
                    existing_admin.is_admin = True
                    user_service = S3DataService(
                        S3User, self.settings.aws_bucket_name
                    )
                    await user_service.update(
                        s3_client, str(existing_admin.id), existing_admin
                    )
                    print(
                        f"👤 Updated existing user to admin: {self.settings.default_admin_username}"
                    )
        except Exception as e:
            # Don't fail startup if admin creation fails
            print(f"⚠️  Could not create default admin: {e}")

    def _discover_and_register_models(self):
        """Discover models in specified packages."""
        discovered_count = 0

        for package_path in self.model_packages:
            models = discover_models(package_path)
            discovered_count += len(models)

            for model in models:
                print(f"📋 Discovered model: {model.__name__}")

        print(f"📊 Total models discovered: {discovered_count}")

    def _generate_routers(self, app: FastAPI):
        """Generate API routers for all registered models."""
        metadata_dict = get_all_metadata()

        for model_name, metadata in metadata_dict.items():
            if metadata.enable_api:
                print(f"🔧 Generating API for {model_name}...")
                router = generate_crud_router(
                    metadata.model_class,
                    self.settings,
                    tags=[metadata.plural_name],
                )
                app.include_router(router)
                print(f"✅ API generated at {metadata.api_prefix}")

    def _setup_admin(self, app: FastAPI):
        """Setup admin interface."""
        print("🎨 Setting up admin interface...")
        admin_html = generate_admin_interface(self.settings)

        @app.get("/admin", response_class=HTMLResponse)
        async def admin_interface():
            return admin_html

        # Mount static files for admin assets
        # In a real implementation, you'd serve CSS/JS files
        print("✅ Admin interface available at /admin")

    def create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        if self._app is None:
            self._app = FastAPI(
                title=self.title,
                description=self.description,
                version=self.version,
                lifespan=self.lifespan,
            )

            # Store settings in app state for dependency injection
            self._app.state.settings = self.settings
            self._app.state.s3_manager = self.s3_manager

            # Add health check endpoint
            @self._app.get("/health")
            async def health_check():
                try:
                    # Quick S3 connection check
                    s3_client = self.s3_manager.get_sync_client()
                    s3_client.list_buckets()
                    s3_ok = True
                except Exception:
                    s3_ok = False

                return {
                    "status": "healthy" if s3_ok else "unhealthy",
                    "s3_connection": s3_ok,
                    "models_registered": len(get_all_metadata()),
                }

            # Add root endpoint
            @self._app.get("/")
            async def root():
                return {
                    "message": f"Welcome to {self.title}",
                    "version": self.version,
                    "models": list(get_all_metadata().keys()),
                    "admin_url": "/admin" if self.enable_admin else None,
                }

        return self._app

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.create_app()


def create_s3verless_app(
    settings: S3verlessSettings | None = None, **kwargs
) -> FastAPI:
    """Convenience function to create an S3verless app."""
    s3verless = S3verless(settings=settings, **kwargs)
    return s3verless.app
