"""Automatic router generation for S3 models."""

import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field, create_model

from s3verless.core.base import BaseS3Model
from s3verless.core.exceptions import S3verlessException
from s3verless.core.query import query
from s3verless.core.registry import get_model_metadata
from s3verless.core.service import S3DataService
from s3verless.core.settings import S3verlessSettings
from s3verless.fastapi.dependencies import get_s3_client, get_s3_service


def check_ownership_factory(model_class: type[BaseS3Model], owner_field: str):
    """Factory to create ownership check dependency for a specific model."""

    async def check_ownership(
        item_id: uuid.UUID,
        request: Request,
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
    ):
        """Check if current user owns the item or is an admin."""
        # Get current user from request state (set by get_current_user dependency)
        current_user = getattr(request.state, "current_user", None)
        if not current_user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Admins can access everything
        if getattr(current_user, "is_admin", False):
            return  # Admin bypass

        # Get the item
        item = await service.get(s3_client, str(item_id))
        if not item:
            raise HTTPException(
                status_code=404, detail=f"{model_class.__name__} not found"
            )

        # Check ownership
        item_owner_id = getattr(item, owner_field, None)
        if item_owner_id != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail=f"You don't have permission to modify this {model_class.__name__}",
            )

        return item

    return check_ownership


def create_list_response_model(model_class: type[BaseS3Model]) -> type[BaseModel]:
    """Create a pydantic model for list responses."""
    model_name = f"{model_class.__name__}ListResponse"

    # Use the actual model class instead of creating a new ItemModel
    return create_model(
        model_name,
        items=(list[model_class], Field(..., description="List of items")),
        total_count=(int, Field(..., description="Total number of items")),
        page=(int, Field(..., description="Current page number")),
        page_size=(int, Field(..., description="Items per page")),
        has_next=(bool, Field(..., description="Whether there is a next page")),
        has_prev=(bool, Field(..., description="Whether there is a previous page")),
    )


def create_filter_model(model_class: type[BaseS3Model]) -> type[BaseModel]:
    """Create a pydantic model for query filters."""
    model_name = f"{model_class.__name__}Filter"
    filter_fields = {}

    # Add filter fields for each model field
    for field_name, field_info in model_class.model_fields.items():
        if field_name.startswith("_"):
            continue

        # Basic equality filter
        filter_fields[field_name] = (field_info.annotation | None, None)

        # Add operator-based filters for appropriate types
        if field_info.annotation in [str, int, float, datetime]:
            filter_fields[f"{field_name}__gt"] = (field_info.annotation | None, None)
            filter_fields[f"{field_name}__gte"] = (field_info.annotation | None, None)
            filter_fields[f"{field_name}__lt"] = (field_info.annotation | None, None)
            filter_fields[f"{field_name}__lte"] = (field_info.annotation | None, None)

        if field_info.annotation == str:
            filter_fields[f"{field_name}__contains"] = (str | None, None)
            filter_fields[f"{field_name}__starts_with"] = (str | None, None)
            filter_fields[f"{field_name}__ends_with"] = (str | None, None)

    return create_model(model_name, **filter_fields)


def generate_crud_router(
    model_class: type[BaseS3Model],
    settings: S3verlessSettings,
    tags: list[str] | None = None,
    dependencies: list[Depends] | None = None,
) -> APIRouter:
    """Generate a complete CRUD router for a model.

    If the model has _require_auth = True, authentication will be automatically
    added to all CRUD operations.
    """

    metadata = get_model_metadata(model_class.__name__)
    if not metadata or not metadata.enable_api:
        raise ValueError(
            f"Model {model_class.__name__} is not registered or API is disabled"
        )

    # Add authentication dependency if model requires it
    router_dependencies = dependencies or []
    if (metadata.require_auth or metadata.require_ownership) and not dependencies:
        # Import here to avoid circular dependency
        from s3verless.fastapi.auth import get_current_user

        router_dependencies = [Depends(get_current_user)]

    router = APIRouter(
        prefix=metadata.api_prefix,
        tags=tags or [model_class.__name__],
        dependencies=router_dependencies,
    )

    # Create response models
    ListResponse = create_list_response_model(model_class)
    FilterModel = create_filter_model(model_class)

    # Create input model (exclude auto-generated fields)
    create_fields = {}
    update_fields = {}
    for field_name, field_info in model_class.model_fields.items():
        if field_name not in [
            "id",
            "created_at",
            "updated_at",
        ] and not field_name.startswith("_"):
            create_fields[field_name] = (field_info.annotation, field_info)
            update_fields[field_name] = (
                field_info.annotation | None,
                field_info.default,
            )

    CreateModel = create_model(f"{model_class.__name__}Create", **create_fields)
    UpdateModel = create_model(f"{model_class.__name__}Update", **update_fields)

    @router.get("/", response_model=ListResponse)
    async def list_items(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
        sort_by: str | None = Query(None, description="Field to sort by"),
        sort_order: str | None = Query(
            "asc", pattern="^(asc|desc)$", description="Sort order"
        ),
        filters: FilterModel = Depends(),
        s3_client=Depends(get_s3_client),
    ):
        """List items with pagination and filtering."""
        try:
            # Build query
            q = query(model_class, s3_client, settings.aws_bucket_name)

            # Apply filters
            filter_dict = filters.model_dump(exclude_unset=True)
            for key, value in filter_dict.items():
                if value is not None:
                    q = q.filter(**{key: value})

            # Apply sorting
            if sort_by:
                order_by_field = f"-{sort_by}" if sort_order == "desc" else sort_by
                q = q.order_by(order_by_field)

            # Get paginated results
            result = await q.paginate(page=page, page_size=page_size)

            return ListResponse(
                items=result.items,
                total_count=result.total_count,
                page=result.page,
                page_size=result.page_size,
                has_next=result.has_next,
                has_prev=result.has_prev,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/", response_model=model_class, status_code=201)
    async def create_item(
        request: Request,
        item: CreateModel,
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
    ):
        """Create a new item."""
        try:
            # Run pre-create hooks
            await _run_hooks(model_class.__name__, "pre_create", item)

            # Create the model instance
            data = item.model_dump()

            # Auto-set owner field if model requires ownership
            if metadata.require_ownership:
                current_user = getattr(request.state, "current_user", None)
                if current_user:
                    data[metadata.owner_field] = str(current_user.id)

            instance = model_class(**data)

            # Save to S3
            saved_instance = await service.create(s3_client, instance)

            # Run post-create hooks
            await _run_hooks(model_class.__name__, "post_create", saved_instance)

            return saved_instance
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/{item_id}", response_model=model_class)
    async def get_item(
        item_id: uuid.UUID = Path(..., description="Item ID"),
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
    ):
        """Get a single item by ID."""
        try:
            item = await service.get(s3_client, str(item_id))
            if not item:
                raise HTTPException(
                    status_code=404, detail=f"{model_class.__name__} not found"
                )
            return item
        except S3verlessException as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Create ownership dependency if needed
    ownership_check = None
    if metadata.require_ownership:
        ownership_check = check_ownership_factory(model_class, metadata.owner_field)

    @router.put("/{item_id}", response_model=model_class)
    async def update_item(
        item_id: uuid.UUID = Path(..., description="Item ID"),
        update_data: UpdateModel = Body(...),
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
        _ownership_check=Depends(ownership_check) if ownership_check else None,
    ):
        """Update an item."""
        try:
            # Get existing item
            existing = await service.get(s3_client, str(item_id))
            if not existing:
                raise HTTPException(
                    status_code=404, detail=f"{model_class.__name__} not found"
                )

            # Ownership already checked by dependency if required

            # Run pre-update hooks
            await _run_hooks(model_class.__name__, "pre_update", existing, update_data)

            # Update fields
            update_dict = update_data.model_dump(exclude_unset=True)
            for key, value in update_dict.items():
                setattr(existing, key, value)

            # Save
            updated = await service.update(s3_client, str(item_id), existing)

            # Run post-update hooks
            await _run_hooks(model_class.__name__, "post_update", updated)

            return updated
        except S3verlessException as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/{item_id}", status_code=204)
    async def delete_item(
        item_id: uuid.UUID = Path(..., description="Item ID"),
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
        _ownership_check=Depends(ownership_check) if ownership_check else None,
    ):
        """Delete an item."""
        try:
            # Get existing item for hooks
            existing = await service.get(s3_client, str(item_id))
            if not existing:
                raise HTTPException(
                    status_code=404, detail=f"{model_class.__name__} not found"
                )

            # Ownership already checked by dependency if required

            # Run pre-delete hooks
            await _run_hooks(model_class.__name__, "pre_delete", existing)

            # Delete
            await service.delete(s3_client, str(item_id))

            # Run post-delete hooks
            await _run_hooks(model_class.__name__, "post_delete", existing)

            return None
        except S3verlessException as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/bulk", response_model=list[model_class], status_code=201)
    async def create_bulk(
        items: list[CreateModel],
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
    ):
        """Create multiple items at once."""
        try:
            created_items = []
            for item_data in items:
                # Run pre-create hooks
                await _run_hooks(model_class.__name__, "pre_create", item_data)

                # Create instance
                instance = model_class(**item_data.model_dump())
                saved = await service.create(s3_client, instance)

                # Run post-create hooks
                await _run_hooks(model_class.__name__, "post_create", saved)

                created_items.append(saved)

            return created_items
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/bulk", status_code=204)
    async def delete_bulk(
        item_ids: list[uuid.UUID] = Body(..., description="List of item IDs to delete"),
        s3_client=Depends(get_s3_client),
        service: S3DataService = Depends(get_s3_service(model_class)),
    ):
        """Delete multiple items at once."""
        try:
            for item_id in item_ids:
                # Get existing item for hooks
                existing = await service.get(s3_client, str(item_id))
                if existing:
                    # Run pre-delete hooks
                    await _run_hooks(model_class.__name__, "pre_delete", existing)

                    # Delete
                    await service.delete(s3_client, str(item_id))

                    # Run post-delete hooks
                    await _run_hooks(model_class.__name__, "post_delete", existing)

            return None
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/search/", response_model=ListResponse)
    async def search_items(
        q: str = Query(..., description="Search query"),
        fields: list[str] = Query(
            ["name", "title", "description"], description="Fields to search in"
        ),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        s3_client=Depends(get_s3_client),
    ):
        """Search items across multiple fields."""
        try:
            # Build query with OR conditions for search fields
            search_query = query(model_class, s3_client, settings.aws_bucket_name)

            # This is a simple implementation - in production you might want
            # to use a proper search service like ElasticSearch
            all_items = await search_query.all()

            # Filter items that match the search query
            matching_items = []
            for item in all_items:
                for field in fields:
                    if hasattr(item, field):
                        field_value = str(getattr(item, field, "")).lower()
                        if q.lower() in field_value:
                            matching_items.append(item)
                            break

            # Apply pagination
            start = (page - 1) * page_size
            end = start + page_size
            paginated_items = matching_items[start:end]

            return ListResponse(
                items=paginated_items,
                total_count=len(matching_items),
                page=page,
                page_size=page_size,
                has_next=end < len(matching_items),
                has_prev=page > 1,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Store router in metadata
    metadata.router = router

    return router


async def _run_hooks(model_name: str, event: str, *args):
    """Run hooks for a model event."""
    metadata = get_model_metadata(model_name)
    if metadata and event in metadata.hooks:
        for hook in metadata.hooks[event]:
            await hook(*args) if asyncio.iscoroutinefunction(hook) else hook(*args)
