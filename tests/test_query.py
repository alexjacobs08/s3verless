"""Tests for S3Query and query builder."""

import json

import pytest

from s3verless.core.base import BaseS3Model
from s3verless.core.query import (
    Filter,
    FilterOperator,
    QueryResult,
    query,
)
from s3verless.core.registry import set_base_s3_path


class Product(BaseS3Model):
    """Test product model."""

    name: str
    category: str
    price: float
    stock: int
    is_active: bool = True


@pytest.fixture
async def s3_with_data(async_mock_s3_client):
    """Create S3 mock with sample data."""
    set_base_s3_path("test/")

    # Create sample products
    products = [
        Product(name="Laptop", category="electronics", price=999.99, stock=10),
        Product(name="Mouse", category="electronics", price=29.99, stock=50),
        Product(name="Shirt", category="clothing", price=19.99, stock=100),
        Product(name="Jeans", category="clothing", price=49.99, stock=75),
        Product(name="Book", category="books", price=14.99, stock=200),
    ]

    # Populate the mock S3 client's storage
    for product in products:
        key = product.s3_key
        await async_mock_s3_client.put_object(
            Bucket="test-bucket",
            Key=key,
            Body=json.dumps(product.model_dump(), default=str),
            ContentType="application/json",
        )

    yield async_mock_s3_client, products


class TestFilter:
    """Tests for Filter class."""

    def test_eq_filter(self):
        """Test equality filter."""
        f = Filter("name", FilterOperator.EQ, "Test")
        assert f.matches({"name": "Test"}) is True
        assert f.matches({"name": "Other"}) is False

    def test_neq_filter(self):
        """Test not equal filter."""
        f = Filter("status", FilterOperator.NEQ, "inactive")
        assert f.matches({"status": "active"}) is True
        assert f.matches({"status": "inactive"}) is False

    def test_gt_filter(self):
        """Test greater than filter."""
        f = Filter("price", FilterOperator.GT, 10)
        assert f.matches({"price": 15}) is True
        assert f.matches({"price": 10}) is False
        assert f.matches({"price": 5}) is False

    def test_gte_filter(self):
        """Test greater than or equal filter."""
        f = Filter("stock", FilterOperator.GTE, 10)
        assert f.matches({"stock": 15}) is True
        assert f.matches({"stock": 10}) is True
        assert f.matches({"stock": 5}) is False

    def test_lt_filter(self):
        """Test less than filter."""
        f = Filter("price", FilterOperator.LT, 100)
        assert f.matches({"price": 50}) is True
        assert f.matches({"price": 100}) is False
        assert f.matches({"price": 150}) is False

    def test_lte_filter(self):
        """Test less than or equal filter."""
        f = Filter("price", FilterOperator.LTE, 100)
        assert f.matches({"price": 50}) is True
        assert f.matches({"price": 100}) is True
        assert f.matches({"price": 150}) is False

    def test_contains_filter(self):
        """Test contains filter."""
        f = Filter("name", FilterOperator.CONTAINS, "test")
        assert f.matches({"name": "testing"}) is True
        assert f.matches({"name": "other"}) is False

    def test_starts_with_filter(self):
        """Test starts_with filter."""
        f = Filter("name", FilterOperator.STARTS_WITH, "pro")
        assert f.matches({"name": "product"}) is True
        assert f.matches({"name": "test"}) is False

    def test_ends_with_filter(self):
        """Test ends_with filter."""
        f = Filter("email", FilterOperator.ENDS_WITH, "@example.com")
        assert f.matches({"email": "user@example.com"}) is True
        assert f.matches({"email": "user@test.com"}) is False

    def test_in_filter(self):
        """Test in filter."""
        f = Filter("status", FilterOperator.IN, ["active", "pending"])
        assert f.matches({"status": "active"}) is True
        assert f.matches({"status": "pending"}) is True
        assert f.matches({"status": "inactive"}) is False

    def test_is_null_filter(self):
        """Test is_null filter."""
        f = Filter("description", FilterOperator.IS_NULL, None)
        assert f.matches({"description": None}) is True
        assert f.matches({"description": "text"}) is False

    def test_is_not_null_filter(self):
        """Test is_not_null filter."""
        f = Filter("description", FilterOperator.IS_NOT_NULL, None)
        assert f.matches({"description": "text"}) is True
        assert f.matches({"description": None}) is False


class TestS3Query:
    """Tests for S3Query class."""

    @pytest.mark.asyncio
    async def test_query_all(self, s3_with_data):
        """Test querying all items."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket")
        results = await q.all()

        assert len(results) == 5
        assert all(isinstance(r, Product) for r in results)

    @pytest.mark.asyncio
    async def test_filter_eq(self, s3_with_data):
        """Test filtering with equality."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").filter(category="electronics")
        results = await q.all()

        assert len(results) == 2
        assert all(r.category == "electronics" for r in results)

    @pytest.mark.asyncio
    async def test_filter_gt(self, s3_with_data):
        """Test filtering with greater than."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").filter(price__gt=50)
        results = await q.all()

        assert len(results) == 1
        assert results[0].name == "Laptop"

    @pytest.mark.asyncio
    async def test_filter_lt(self, s3_with_data):
        """Test filtering with less than."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").filter(price__lt=20)
        results = await q.all()

        assert len(results) == 2  # Shirt and Book

    @pytest.mark.asyncio
    async def test_filter_contains(self, s3_with_data):
        """Test filtering with contains."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").filter(name__contains="o")
        results = await q.all()

        # Laptop, Mouse, Book have 'o'
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_multiple_filters(self, s3_with_data):
        """Test combining multiple filters."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").filter(
            category="electronics", price__lt=100
        )
        results = await q.all()

        assert len(results) == 1
        assert results[0].name == "Mouse"

    @pytest.mark.asyncio
    async def test_order_by_asc(self, s3_with_data):
        """Test ordering results ascending."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").order_by("price")
        results = await q.all()

        prices = [r.price for r in results]
        assert prices == sorted(prices)

    @pytest.mark.asyncio
    async def test_order_by_desc(self, s3_with_data):
        """Test ordering results descending."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").order_by("-price")
        results = await q.all()

        prices = [r.price for r in results]
        assert prices == sorted(prices, reverse=True)

    @pytest.mark.asyncio
    async def test_limit(self, s3_with_data):
        """Test limiting results."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").limit(3)
        results = await q.all()

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_offset(self, s3_with_data):
        """Test offset in results."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").order_by("name").offset(2)
        results = await q.all()

        assert len(results) == 3  # Total 5 - offset 2

    @pytest.mark.asyncio
    async def test_limit_and_offset(self, s3_with_data):
        """Test combining limit and offset."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").order_by("name").offset(1).limit(2)
        results = await q.all()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_first(self, s3_with_data):
        """Test getting first result."""
        client, products = s3_with_data

        result = (
            await query(Product, client, "test-bucket")
            .filter(category="electronics")
            .first()
        )

        assert result is not None
        assert isinstance(result, Product)
        assert result.category == "electronics"

    @pytest.mark.asyncio
    async def test_first_empty(self, s3_with_data):
        """Test first() with no results."""
        client, products = s3_with_data

        result = (
            await query(Product, client, "test-bucket")
            .filter(category="nonexistent")
            .first()
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_count(self, s3_with_data):
        """Test counting results."""
        client, products = s3_with_data

        count = (
            await query(Product, client, "test-bucket")
            .filter(category="electronics")
            .count()
        )

        assert count == 2

    @pytest.mark.asyncio
    async def test_exists(self, s3_with_data):
        """Test checking if results exist."""
        client, products = s3_with_data

        exists = (
            await query(Product, client, "test-bucket")
            .filter(category="electronics")
            .exists()
        )

        assert exists is True

        not_exists = (
            await query(Product, client, "test-bucket")
            .filter(category="nonexistent")
            .exists()
        )

        assert not_exists is False

    @pytest.mark.asyncio
    async def test_paginate(self, s3_with_data):
        """Test pagination."""
        client, products = s3_with_data

        result = await query(Product, client, "test-bucket").paginate(
            page=1, page_size=2
        )

        assert isinstance(result, QueryResult)
        assert len(result.items) == 2
        assert result.total_count == 5
        assert result.page == 1
        assert result.page_size == 2
        assert result.has_next is True
        assert result.has_prev is False

    @pytest.mark.asyncio
    async def test_paginate_last_page(self, s3_with_data):
        """Test pagination on last page."""
        client, products = s3_with_data

        result = await query(Product, client, "test-bucket").paginate(
            page=3, page_size=2
        )

        assert len(result.items) == 1  # Only 1 item on last page
        assert result.has_next is False
        assert result.has_prev is True

    @pytest.mark.asyncio
    async def test_exclude(self, s3_with_data):
        """Test excluding items."""
        client, products = s3_with_data

        q = query(Product, client, "test-bucket").exclude(category="electronics")
        results = await q.all()

        assert len(results) == 3  # 5 total - 2 electronics
        assert all(r.category != "electronics" for r in results)
