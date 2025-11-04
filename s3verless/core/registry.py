"""Registry for S3 models and configuration."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from s3verless.core.base import BaseS3Model

# Global registry for model classes
_model_registry: dict[str, type["BaseS3Model"]] = {}

# Global configuration for the base S3 path
_base_s3_path: str = ""


# Model metadata storage
@dataclass
class ModelMetadata:
    """Metadata for registered models."""

    model_class: type["BaseS3Model"]
    plural_name: str
    api_prefix: str
    router: APIRouter | None = None
    indexes: dict[str, list[str]] = field(
        default_factory=dict
    )  # field_name -> [index_type]
    unique_fields: list[str] = field(default_factory=list)  # list of unique field names
    relationships: dict[str, str] = field(
        default_factory=dict
    )  # field_name -> related_model
    hooks: dict[str, list[Callable]] = field(
        default_factory=dict
    )  # event -> [callbacks]
    enable_api: bool = True
    enable_admin: bool = True
    require_auth: bool = False  # If True, all CRUD operations require authentication
    require_ownership: bool = (
        False  # If True, users can only modify their own resources
    )
    owner_field: str = "user_id"  # Field name that contains the owner's user ID
    permissions: dict[str, list[str]] = field(
        default_factory=dict
    )  # action -> [required_permissions]


_model_metadata: dict[str, ModelMetadata] = {}


def register_model(model_cls: type["BaseS3Model"]) -> None:
    """Register a model class derived from BaseS3Model.

    Note: Metadata creation is deferred to first access to ensure class
    attributes are fully initialized."""
    model_name = model_cls.__name__
    if model_name in _model_registry:
        # Potentially warn about re-registration if needed
        pass
    _model_registry[model_name] = model_cls
    print(
        f"Registered s3verless model: {model_name}"
    )  # Temporary print for verification


def _ensure_metadata(model_name: str) -> None:
    """Create metadata for a model if it doesn't exist yet.

    This is called lazily to ensure class attributes are fully initialized."""
    if model_name in _model_metadata:
        return

    model_cls = _model_registry.get(model_name)
    if not model_cls:
        return

    # Get class attributes (they should be available now, after class construction)
    plural_name = getattr(model_cls, "_plural_name", "") or f"{model_name.lower()}s"
    api_prefix = getattr(model_cls, "_api_prefix", "") or f"/{plural_name}"
    indexes_list = getattr(model_cls, "_indexes", []) or []
    unique_fields_list = getattr(model_cls, "_unique_fields", []) or []

    _model_metadata[model_name] = ModelMetadata(
        model_class=model_cls,
        plural_name=plural_name,
        api_prefix=api_prefix,
        enable_api=getattr(model_cls, "_enable_api", True),
        enable_admin=getattr(model_cls, "_enable_admin", True),
        require_auth=getattr(model_cls, "_require_auth", False),
        require_ownership=getattr(model_cls, "_require_ownership", False),
        owner_field=getattr(model_cls, "_owner_field", "user_id"),
    )

    # Add indexes and unique fields
    for index in indexes_list:
        _model_metadata[model_name].indexes[index] = ["default"]

    _model_metadata[model_name].unique_fields = list(unique_fields_list)


def get_model(model_name: str) -> type["BaseS3Model"] | None:
    """Get a registered model class by name."""
    return _model_registry.get(model_name)


def set_base_s3_path(path: str) -> None:
    """Set the global base S3 path for models."""
    global _base_s3_path
    if not path:
        _base_s3_path = ""  # Reset or handle empty path
    elif not path.endswith("/"):
        _base_s3_path = f"{path}/"
    else:
        _base_s3_path = path
    print(f"s3verless base path set to: '{_base_s3_path}'")  # Temporary print


def get_base_s3_path() -> str:
    """Get the configured global base S3 path."""
    return _base_s3_path


def get_model_s3_prefix(model_cls: type["BaseS3Model"]) -> str:
    """Calculate the S3 prefix for a given model class."""
    base_path = get_base_s3_path()
    # Get the plural name from metadata, fallback to model name if not available
    model_name = model_cls.__name__
    metadata = get_model_metadata(model_name)
    if metadata and metadata.plural_name:
        folder_name = metadata.plural_name
    else:
        folder_name = model_name.lower()
    # Example: base_path='data/', plural_name='items' -> 'data/items/'
    return f"{base_path}{folder_name}/"


def get_all_models() -> dict[str, type["BaseS3Model"]]:
    """Get all registered model classes."""
    return _model_registry.copy()


def get_model_metadata(model_name: str) -> ModelMetadata | None:
    """Get metadata for a registered model."""
    _ensure_metadata(model_name)
    return _model_metadata.get(model_name)


def get_all_metadata() -> dict[str, ModelMetadata]:
    """Get all model metadata."""
    # Ensure metadata exists for all registered models
    for model_name in _model_registry.keys():
        _ensure_metadata(model_name)
    return _model_metadata.copy()


def add_model_index(model_name: str, field_name: str, index_type: str = "hash") -> None:
    """Add an index to a model field."""
    if model_name in _model_metadata:
        if field_name not in _model_metadata[model_name].indexes:
            _model_metadata[model_name].indexes[field_name] = []
        _model_metadata[model_name].indexes[field_name].append(index_type)


def add_model_relationship(
    model_name: str, field_name: str, related_model: str
) -> None:
    """Add a relationship between models."""
    if model_name in _model_metadata:
        _model_metadata[model_name].relationships[field_name] = related_model


def add_model_hook(model_name: str, event: str, callback: Callable) -> None:
    """Add a hook to a model for lifecycle events."""
    if model_name in _model_metadata:
        if event not in _model_metadata[model_name].hooks:
            _model_metadata[model_name].hooks[event] = []
        _model_metadata[model_name].hooks[event].append(callback)
