# Queries Guide

Filter, sort, and paginate your S3 data with the fluent Query API.

## Basic Usage

```python
from s3verless.core.query import Query

# Get all products
products = await Query(Product, s3_client, "my-bucket").all()

# Get first product
product = await Query(Product, s3_client, "my-bucket").first()

# Count products
count = await Query(Product, s3_client, "my-bucket").count()
```

## Filtering

### Exact Match

```python
# Single filter
products = await (
    Query(Product, s3_client, bucket)
    .filter(category="electronics")
    .all()
)

# Multiple filters (AND)
products = await (
    Query(Product, s3_client, bucket)
    .filter(category="electronics", in_stock=True)
    .all()
)
```

### Comparison Operators

```python
# Greater than
products = await Query(Product, s3_client, bucket).filter(price__gt=100).all()

# Less than or equal
products = await Query(Product, s3_client, bucket).filter(price__lte=50).all()

# Not equal
products = await Query(Product, s3_client, bucket).filter(status__ne="archived").all()
```

**Available operators:**
- `__eq` - Equal (default)
- `__ne` - Not equal
- `__gt` - Greater than
- `__gte` - Greater than or equal
- `__lt` - Less than
- `__lte` - Less than or equal

### List Membership

```python
# In list
products = await (
    Query(Product, s3_client, bucket)
    .filter(category__in=["electronics", "computers"])
    .all()
)

# Not in list
products = await (
    Query(Product, s3_client, bucket)
    .filter(status__nin=["archived", "deleted"])
    .all()
)
```

### String Matching

```python
# Contains (case-sensitive)
products = await Query(Product, s3_client, bucket).filter(name__contains="Pro").all()

# Contains (case-insensitive)
products = await Query(Product, s3_client, bucket).filter(name__icontains="pro").all()

# Starts with
products = await Query(Product, s3_client, bucket).filter(sku__startswith="ELEC-").all()

# Ends with
products = await Query(Product, s3_client, bucket).filter(name__endswith="Edition").all()
```

### Null Checks

```python
# Is null
products = await Query(Product, s3_client, bucket).filter(description__isnull=True).all()

# Is not null
products = await Query(Product, s3_client, bucket).filter(description__isnull=False).all()
```

## Exclusion

Use `exclude()` to negate conditions:

```python
# Exclude archived products
products = await (
    Query(Product, s3_client, bucket)
    .filter(category="electronics")
    .exclude(status="archived")
    .all()
)
```

## Sorting

```python
# Ascending (default)
products = await Query(Product, s3_client, bucket).order_by("price").all()

# Descending (prefix with -)
products = await Query(Product, s3_client, bucket).order_by("-created_at").all()
```

## Limiting Results

```python
# Limit
products = await Query(Product, s3_client, bucket).limit(10).all()

# Offset
products = await Query(Product, s3_client, bucket).offset(20).limit(10).all()
```

## Pagination

```python
from s3verless.core.query import QueryResult

result: QueryResult = await (
    Query(Product, s3_client, bucket)
    .filter(category="electronics")
    .order_by("-price")
    .paginate(page=1, page_size=20)
)

print(result.items)       # List of products
print(result.total_count) # Total matching products
print(result.page)        # Current page (1)
print(result.page_size)   # Items per page (20)
print(result.has_next)    # True if more pages exist
print(result.has_prev)    # False for first page
```

## Field Selection

Select specific fields to reduce data transfer:

```python
products = await (
    Query(Product, s3_client, bucket)
    .select("id", "name", "price")
    .all()
)
```

## Getting Single Results

```python
# Get first or None
product = await Query(Product, s3_client, bucket).filter(sku="ABC123").first()

# Get exactly one (raises if 0 or >1)
product = await Query(Product, s3_client, bucket).filter(sku="ABC123").get()

# Check existence
exists = await Query(Product, s3_client, bucket).filter(sku="ABC123").exists()
```

## Chaining

All methods return the query for chaining:

```python
products = await (
    Query(Product, s3_client, bucket)
    .filter(category="electronics")
    .filter(price__gte=50)
    .exclude(status="archived")
    .order_by("-rating")
    .select("id", "name", "price", "rating")
    .limit(10)
    .all()
)
```

## Performance Tips

1. **Use indexed fields** - Define `_indexed_fields` on models
2. **Limit results** - Always use `.limit()` or `.paginate()`
3. **Select fields** - Use `.select()` if you don't need all fields
4. **Filter early** - Put most selective filters first

## Example: Search API

```python
@app.get("/products/search")
async def search_products(
    q: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: str = "-created_at",
    page: int = 1,
    page_size: int = 20,
):
    query = Query(Product, s3_client, bucket)

    if q:
        query = query.filter(name__icontains=q)
    if category:
        query = query.filter(category=category)
    if min_price:
        query = query.filter(price__gte=min_price)
    if max_price:
        query = query.filter(price__lte=max_price)

    return await query.order_by(sort).paginate(page, page_size)
```
