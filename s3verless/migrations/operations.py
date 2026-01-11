"""Built-in migration operations for S3verless."""

from dataclasses import dataclass
from typing import Any, Callable

from s3verless.migrations.base import MigrationOperation


@dataclass
class AddField(MigrationOperation):
    """Add a new field with a default value.

    Example:
        AddField("is_active", default=True)
    """

    field_name: str
    default: Any = None
    default_factory: Callable[[], Any] | None = None

    def forward(self, data: dict) -> dict:
        result = data.copy()
        if self.field_name not in result:
            if self.default_factory:
                result[self.field_name] = self.default_factory()
            else:
                result[self.field_name] = self.default
        return result

    def reverse(self, data: dict) -> dict:
        result = data.copy()
        result.pop(self.field_name, None)
        return result


@dataclass
class RemoveField(MigrationOperation):
    """Remove a field from objects.

    Note: This operation stores the removed value for rollback.

    Example:
        RemoveField("deprecated_field")
    """

    field_name: str
    _removed_values: dict = None  # Stores values for rollback

    def __post_init__(self):
        self._removed_values = {}

    def forward(self, data: dict) -> dict:
        result = data.copy()
        if self.field_name in result:
            # Store for potential rollback
            obj_id = result.get("id", "unknown")
            self._removed_values[obj_id] = result.pop(self.field_name)
        return result

    def reverse(self, data: dict) -> dict:
        result = data.copy()
        obj_id = result.get("id", "unknown")
        if obj_id in self._removed_values:
            result[self.field_name] = self._removed_values[obj_id]
        return result


@dataclass
class RenameField(MigrationOperation):
    """Rename a field.

    Example:
        RenameField("old_name", "new_name")
    """

    old_name: str
    new_name: str

    def forward(self, data: dict) -> dict:
        result = data.copy()
        if self.old_name in result:
            result[self.new_name] = result.pop(self.old_name)
        return result

    def reverse(self, data: dict) -> dict:
        result = data.copy()
        if self.new_name in result:
            result[self.old_name] = result.pop(self.new_name)
        return result


@dataclass
class TransformField(MigrationOperation):
    """Transform a field value using a custom function.

    Example:
        TransformField(
            "price",
            forward_func=lambda x: x * 100,  # dollars to cents
            reverse_func=lambda x: x / 100,  # cents to dollars
        )
    """

    field_name: str
    forward_func: Callable[[Any], Any]
    reverse_func: Callable[[Any], Any] | None = None

    def forward(self, data: dict) -> dict:
        result = data.copy()
        if self.field_name in result:
            result[self.field_name] = self.forward_func(result[self.field_name])
        return result

    def reverse(self, data: dict) -> dict:
        if self.reverse_func is None:
            raise NotImplementedError(
                f"TransformField for '{self.field_name}' has no reverse function"
            )
        result = data.copy()
        if self.field_name in result:
            result[self.field_name] = self.reverse_func(result[self.field_name])
        return result


@dataclass
class ChangeFieldType(MigrationOperation):
    """Change a field's type.

    Example:
        ChangeFieldType("count", converter=int)
    """

    field_name: str
    converter: Callable[[Any], Any]
    reverse_converter: Callable[[Any], Any] | None = None

    def forward(self, data: dict) -> dict:
        result = data.copy()
        if self.field_name in result:
            result[self.field_name] = self.converter(result[self.field_name])
        return result

    def reverse(self, data: dict) -> dict:
        if self.reverse_converter is None:
            raise NotImplementedError(
                f"ChangeFieldType for '{self.field_name}' has no reverse converter"
            )
        result = data.copy()
        if self.field_name in result:
            result[self.field_name] = self.reverse_converter(result[self.field_name])
        return result


@dataclass
class RenameModel(MigrationOperation):
    """Rename a model (changes S3 prefix).

    Note: This is a special operation that affects the S3 path,
    not just the data. It requires special handling in the runner.

    Example:
        RenameModel("OldModel", "NewModel")
    """

    old_name: str
    new_name: str

    def forward(self, data: dict) -> dict:
        # Data transformation not needed; handled at storage level
        return data

    def reverse(self, data: dict) -> dict:
        return data


@dataclass
class SplitField(MigrationOperation):
    """Split a single field into multiple fields.

    Example:
        SplitField(
            "full_name",
            target_fields=["first_name", "last_name"],
            splitter=lambda x: x.split(" ", 1),
        )
    """

    source_field: str
    target_fields: list[str]
    splitter: Callable[[Any], list[Any]]
    joiner: Callable[[list[Any]], Any] | None = None

    def forward(self, data: dict) -> dict:
        result = data.copy()
        if self.source_field in result:
            values = self.splitter(result.pop(self.source_field))
            for i, field_name in enumerate(self.target_fields):
                if i < len(values):
                    result[field_name] = values[i]
        return result

    def reverse(self, data: dict) -> dict:
        if self.joiner is None:
            raise NotImplementedError(
                f"SplitField from '{self.source_field}' has no joiner function"
            )
        result = data.copy()
        values = [result.pop(f, None) for f in self.target_fields]
        result[self.source_field] = self.joiner(values)
        return result


@dataclass
class MergeFields(MigrationOperation):
    """Merge multiple fields into a single field.

    Example:
        MergeFields(
            ["first_name", "last_name"],
            target_field="full_name",
            merger=lambda x: " ".join(x),
        )
    """

    source_fields: list[str]
    target_field: str
    merger: Callable[[list[Any]], Any]
    splitter: Callable[[Any], list[Any]] | None = None

    def forward(self, data: dict) -> dict:
        result = data.copy()
        values = [result.pop(f, None) for f in self.source_fields]
        result[self.target_field] = self.merger(values)
        return result

    def reverse(self, data: dict) -> dict:
        if self.splitter is None:
            raise NotImplementedError(
                f"MergeFields to '{self.target_field}' has no splitter function"
            )
        result = data.copy()
        if self.target_field in result:
            values = self.splitter(result.pop(self.target_field))
            for i, field_name in enumerate(self.source_fields):
                if i < len(values):
                    result[field_name] = values[i]
        return result


@dataclass
class ConditionalTransform(MigrationOperation):
    """Apply transformation only if a condition is met.

    Example:
        ConditionalTransform(
            condition=lambda x: x.get("type") == "premium",
            operation=AddField("premium_features", default=[]),
        )
    """

    condition: Callable[[dict], bool]
    operation: MigrationOperation

    def forward(self, data: dict) -> dict:
        if self.condition(data):
            return self.operation.forward(data)
        return data.copy()

    def reverse(self, data: dict) -> dict:
        if self.condition(data):
            return self.operation.reverse(data)
        return data.copy()
