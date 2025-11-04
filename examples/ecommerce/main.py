"""
E-commerce Product Catalog Example using S3verless

This example demonstrates:
- Product management
- Inventory tracking
- Categories and search
- Price management
"""

from enum import Enum

from s3verless import BaseS3Model, create_s3verless_app
from s3verless.core.settings import S3verlessSettings


class ProductStatus(str, Enum):
    """Product availability status."""

    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class Category(BaseS3Model):
    """Product category."""

    _plural_name = "categories"
    _api_prefix = "/api/categories"

    name: str
    slug: str
    description: str | None = None
    parent_category_id: str | None = None
    image_url: str | None = None
    is_active: bool = True
    sort_order: int = 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Electronics",
                "slug": "electronics",
                "description": "Electronic devices and accessories",
                "is_active": True,
            }
        }
    }


class Product(BaseS3Model):
    """Product in the catalog."""

    _plural_name = "products"
    _api_prefix = "/api/products"
    _indexes = ["category_id", "sku", "status"]
    _unique_fields = ["sku"]

    # Basic Info
    name: str
    slug: str
    sku: str  # Stock Keeping Unit
    description: str
    short_description: str | None = None

    # Pricing
    price: float
    compare_at_price: float | None = None  # Original price for sale items
    cost: float | None = None  # For profit calculations

    # Inventory
    quantity: int = 0
    low_stock_threshold: int = 10
    status: ProductStatus = ProductStatus.ACTIVE

    # Organization
    category_id: str
    category_name: str  # Denormalized
    tags: list[str] = []
    brand: str | None = None

    # Media
    images: list[str] = []  # URLs to product images
    primary_image: str | None = None

    # Attributes
    attributes: dict[str, str] = {}  # Size, Color, etc.

    # SEO
    meta_title: str | None = None
    meta_description: str | None = None

    # Metrics
    views: int = 0
    sales_count: int = 0
    rating: float = 0.0
    review_count: int = 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Wireless Bluetooth Headphones",
                "slug": "wireless-bluetooth-headphones",
                "sku": "AUDIO-WH-001",
                "description": "High-quality wireless headphones with noise cancellation",
                "price": 99.99,
                "compare_at_price": 149.99,
                "quantity": 50,
                "category_id": "cat-123",
                "category_name": "Electronics",
                "tags": ["audio", "wireless", "bluetooth"],
                "brand": "AudioTech",
                "attributes": {"color": "Black", "battery_life": "30 hours"},
            }
        }
    }


class Review(BaseS3Model):
    """Product review."""

    _plural_name = "reviews"
    _api_prefix = "/api/reviews"
    _indexes = ["product_id", "user_id"]

    product_id: str
    product_name: str  # Denormalized
    user_id: str
    user_name: str
    rating: int  # 1-5 stars
    title: str
    content: str
    verified_purchase: bool = False
    helpful_count: int = 0
    is_approved: bool = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "prod-123",
                "product_name": "Wireless Bluetooth Headphones",
                "user_id": "user-456",
                "user_name": "John D.",
                "rating": 5,
                "title": "Excellent sound quality!",
                "content": "These headphones are amazing...",
                "verified_purchase": True,
            }
        }
    }


class Order(BaseS3Model):
    """Customer order."""

    _plural_name = "orders"
    _api_prefix = "/api/orders"
    _indexes = ["customer_id", "status"]

    order_number: str
    customer_id: str
    customer_email: str

    # Order items (simplified - in production might be separate model)
    items: list[dict] = []  # [{"product_id": "...", "quantity": 2, "price": 99.99}]

    # Totals
    subtotal: float
    tax: float = 0.0
    shipping: float = 0.0
    discount: float = 0.0
    total: float

    # Status
    status: str = "pending"  # pending, processing, shipped, delivered, cancelled
    payment_status: str = "pending"  # pending, paid, failed, refunded

    # Shipping
    shipping_address: dict = {}
    billing_address: dict = {}
    tracking_number: str | None = None

    # Metadata
    notes: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "order_number": "ORD-2024-00001",
                "customer_id": "cust-123",
                "customer_email": "customer@example.com",
                "items": [
                    {
                        "product_id": "prod-123",
                        "name": "Wireless Headphones",
                        "quantity": 1,
                        "price": 99.99,
                    }
                ],
                "subtotal": 99.99,
                "tax": 8.00,
                "shipping": 5.00,
                "total": 112.99,
                "status": "pending",
            }
        }
    }


# Create the FastAPI app with sensible defaults
settings = S3verlessSettings(
    aws_bucket_name="ecommerce-bucket", secret_key="dev-secret-key-change-in-production"
)
app = create_s3verless_app(
    settings=settings,
    title="E-commerce API",
    description="Product catalog and order management API powered by S3verless",
    version="1.0.0",
    enable_admin=True,
)


@app.get("/api/products/{product_id}/reviews")
async def get_product_reviews(product_id: str):
    """Get all reviews for a product."""
    # In a real app, query reviews by product_id
    return {
        "product_id": product_id,
        "reviews": [],
        "average_rating": 0.0,
        "total_reviews": 0,
    }


@app.get("/api/low-stock")
async def get_low_stock_products():
    """Get products with low inventory."""
    # In a real app, query products where quantity <= low_stock_threshold
    return {"products": [], "count": 0}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
