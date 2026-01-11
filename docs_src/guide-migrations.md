# Migrations Guide

Evolve your data schema without losing existing data.

## Overview

S3verless migrations transform existing JSON objects in S3 when your model schema changes. Unlike SQL migrations, they modify each object's data directly.

## Creating Migrations

### Basic Migration

```python
# migrations/0001_add_status_field.py
from s3verless.migrations.base import Migration

migration = Migration(
    version="0001",
    model_name="Product",
    description="Add status field with default 'active'",
    apply=lambda data: {**data, "status": "active"},
    rollback=lambda data: {k: v for k, v in data.items() if k != "status"},
    reversible=True,
)
```

### Migration with Logic

```python
# migrations/0002_split_name.py
from s3verless.migrations.base import Migration

def apply_split_name(data):
    """Split 'name' into 'first_name' and 'last_name'."""
    if "name" in data and "first_name" not in data:
        parts = data["name"].split(" ", 1)
        return {
            **{k: v for k, v in data.items() if k != "name"},
            "first_name": parts[0],
            "last_name": parts[1] if len(parts) > 1 else "",
        }
    return data

def rollback_split_name(data):
    """Merge 'first_name' and 'last_name' back to 'name'."""
    if "first_name" in data:
        name = data.get("first_name", "")
        if data.get("last_name"):
            name += " " + data["last_name"]
        return {
            **{k: v for k, v in data.items() if k not in ("first_name", "last_name")},
            "name": name,
        }
    return data

migration = Migration(
    version="0002",
    model_name="User",
    description="Split name into first_name and last_name",
    apply=apply_split_name,
    rollback=rollback_split_name,
    reversible=True,
)
```

## Running Migrations

### Using MigrationRunner

```python
from pathlib import Path
from s3verless.migrations.runner import MigrationRunner

runner = MigrationRunner(
    s3_client,
    bucket_name="my-bucket",
    migrations_dir=Path("./migrations"),
)

# Run all pending migrations
results = await runner.run_pending()
for result in results:
    print(f"{result['version']}: {result['status']} - {result['objects_transformed']} objects")
```

### Programmatic Registration

```python
runner = MigrationRunner(s3_client, bucket_name)
runner.register(migration)
await runner.run_pending()
```

### Check Applied Migrations

```python
applied = await runner.get_applied_migrations()
print(f"Applied: {applied}")  # ["0001", "0002"]

pending = runner.get_pending_migrations()
print(f"Pending: {[m.version for m in pending]}")
```

## Rollback

```python
# Rollback a specific migration
result = await runner.rollback("0002")
print(f"Rolled back {result['objects_transformed']} objects")
```

Only migrations marked `reversible=True` can be rolled back.

## Migration Patterns

### Adding a Field

```python
Migration(
    version="0001",
    model_name="Product",
    description="Add rating field",
    apply=lambda data: {**data, "rating": 0.0},
    rollback=lambda data: {k: v for k, v in data.items() if k != "rating"},
    reversible=True,
)
```

### Removing a Field

```python
Migration(
    version="0002",
    model_name="Product",
    description="Remove deprecated field",
    apply=lambda data: {k: v for k, v in data.items() if k != "old_field"},
    rollback=lambda data: {**data, "old_field": None},  # Can't restore data
    reversible=False,  # Mark as irreversible
)
```

### Renaming a Field

```python
def rename_field(data):
    if "old_name" in data:
        return {
            **{k: v for k, v in data.items() if k != "old_name"},
            "new_name": data["old_name"],
        }
    return data

def unrename_field(data):
    if "new_name" in data:
        return {
            **{k: v for k, v in data.items() if k != "new_name"},
            "old_name": data["new_name"],
        }
    return data

Migration(
    version="0003",
    model_name="Product",
    description="Rename old_name to new_name",
    apply=rename_field,
    rollback=unrename_field,
    reversible=True,
)
```

### Converting Data Types

```python
def convert_price_to_cents(data):
    if "price" in data and isinstance(data["price"], float):
        return {**data, "price": int(data["price"] * 100)}
    return data

def convert_price_to_dollars(data):
    if "price" in data and isinstance(data["price"], int):
        return {**data, "price": data["price"] / 100}
    return data

Migration(
    version="0004",
    model_name="Product",
    description="Convert price from dollars to cents",
    apply=convert_price_to_cents,
    rollback=convert_price_to_dollars,
    reversible=True,
)
```

### Restructuring Data

```python
def flatten_address(data):
    if "address" in data and isinstance(data["address"], dict):
        addr = data["address"]
        return {
            **{k: v for k, v in data.items() if k != "address"},
            "street": addr.get("street", ""),
            "city": addr.get("city", ""),
            "zip": addr.get("zip", ""),
        }
    return data

Migration(
    version="0005",
    model_name="User",
    description="Flatten nested address object",
    apply=flatten_address,
    reversible=False,  # Hard to reverse reliably
)
```

## Migration History

Migrations are tracked in `_system/migration_history.json`:

```json
{
  "records": [
    {
      "version": "0001",
      "model_name": "Product",
      "description": "Add status field",
      "applied_at": "2024-01-15T10:30:00Z",
      "objects_transformed": 150
    }
  ]
}
```

## Best Practices

1. **Version sequentially** - Use `0001`, `0002`, etc.
2. **One change per migration** - Easier to rollback
3. **Test migrations** - Run on copy of data first
4. **Make reversible when possible** - But mark irreversible if data loss occurs
5. **Handle missing fields** - Check if field exists before transforming
6. **Document changes** - Clear descriptions help future you
7. **Backup before running** - S3 versioning or manual backup

## CLI Integration

You can create a CLI command for migrations:

```python
import asyncio
from pathlib import Path

async def run_migrations():
    runner = MigrationRunner(s3_client, bucket_name, Path("./migrations"))
    results = await runner.run_pending()
    for r in results:
        print(f"{r['version']}: {r['status']}")

if __name__ == "__main__":
    asyncio.run(run_migrations())
```
