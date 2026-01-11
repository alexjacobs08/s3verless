"""Model factories for testing S3verless applications."""

from typing import Type, TypeVar, Generic

from s3verless.core.base import BaseS3Model
from s3verless.core.service import S3DataService
from s3verless.seeding.generator import DataGenerator

T = TypeVar("T", bound=BaseS3Model)


class ModelFactory(Generic[T]):
    """Factory for creating model instances in tests.

    This class makes it easy to create model instances with fake data
    for testing purposes.

    Example:
        >>> class Product(BaseS3Model):
        ...     name: str
        ...     price: float
        ...
        >>> factory = ModelFactory(Product)
        >>> product = factory.build(name="Custom Name")
        >>> assert product.name == "Custom Name"
        >>> assert product.price > 0  # Auto-generated
    """

    def __init__(
        self,
        model_class: Type[T],
        locale: str = "en_US",
        defaults: dict | None = None,
    ):
        """Initialize the factory.

        Args:
            model_class: The model class to create instances of
            locale: Locale for fake data generation
            defaults: Default values to use for all instances
        """
        self.model_class = model_class
        self.generator = DataGenerator(locale=locale)
        self.defaults = defaults or {}

    def build(self, **overrides) -> T:
        """Build a model instance without saving to S3.

        Args:
            **overrides: Field values to override generated data

        Returns:
            A new model instance
        """
        data = self.generator.generate_instance(self.model_class)
        data.update(self.defaults)
        data.update(overrides)
        return self.model_class(**data)

    def build_batch(self, count: int, **overrides) -> list[T]:
        """Build multiple model instances.

        Args:
            count: Number of instances to build
            **overrides: Field values to override in all instances

        Returns:
            List of model instances
        """
        return [self.build(**overrides) for _ in range(count)]

    async def create(
        self,
        s3_client,
        bucket: str,
        **overrides
    ) -> T:
        """Create and save a model instance to S3.

        Args:
            s3_client: The S3 client to use
            bucket: The S3 bucket name
            **overrides: Field values to override generated data

        Returns:
            The created model instance
        """
        instance = self.build(**overrides)
        service = S3DataService(self.model_class, bucket)
        return await service.create(s3_client, instance)

    async def create_batch(
        self,
        s3_client,
        bucket: str,
        count: int,
        **overrides
    ) -> list[T]:
        """Create and save multiple model instances to S3.

        Args:
            s3_client: The S3 client to use
            bucket: The S3 bucket name
            count: Number of instances to create
            **overrides: Field values to override in all instances

        Returns:
            List of created model instances
        """
        service = S3DataService(self.model_class, bucket)
        instances = []
        for _ in range(count):
            instance = self.build(**overrides)
            created = await service.create(s3_client, instance)
            instances.append(created)
        return instances

    def with_defaults(self, **defaults) -> "ModelFactory[T]":
        """Create a new factory with additional defaults.

        Args:
            **defaults: Default values to merge with existing defaults

        Returns:
            A new ModelFactory instance with merged defaults
        """
        merged_defaults = {**self.defaults, **defaults}
        return ModelFactory(
            self.model_class,
            locale=self.generator.locale,
            defaults=merged_defaults,
        )


def factory_for(model_class: Type[T], **defaults) -> ModelFactory[T]:
    """Create a factory for a model class.

    Convenience function for creating model factories.

    Args:
        model_class: The model class
        **defaults: Default values for all instances

    Returns:
        A ModelFactory instance

    Example:
        >>> ProductFactory = factory_for(Product, is_active=True)
        >>> product = ProductFactory.build()
    """
    return ModelFactory(model_class, defaults=defaults)
