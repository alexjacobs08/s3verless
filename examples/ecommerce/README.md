# E-commerce Product Catalog Example

A complete e-commerce product catalog system demonstrating inventory management, product organization, and order processing.

## Features

- **Product Management**: Full product catalog with SKUs, pricing, and inventory
- **Categories**: Hierarchical category system
- **Reviews**: Customer reviews and ratings
- **Orders**: Order processing and tracking
- **Inventory Tracking**: Stock levels and low-stock alerts
- **Search & Filter**: Find products by category, tags, price, etc.
- **Analytics**: Track views, sales, and ratings

## Models

### Product
- Name, SKU, description
- Pricing (regular, sale, cost)
- Inventory management
- Categories and tags
- Images and attributes
- SEO metadata
- Metrics (views, sales, ratings)

### Category
- Hierarchical categories
- Images and descriptions
- Active/inactive status

### Review
- Product ratings (1-5 stars)
- Review content
- Verified purchase badge
- Moderation

### Order
- Order items and totals
- Payment and shipping status
- Tracking information
- Customer details

## Setup

```bash
# Install dependencies
# Using uv (recommended)
uv pip install s3verless uvicorn

# Or using pip
# pip install s3verless uvicorn

# Start LocalStack (for local development)
docker run -d -p 4566:4566 localstack/localstack

# Set environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_BUCKET_NAME=ecommerce-catalog
export SECRET_KEY=your-secret-key

# Run the application
python main.py
```

**Note**: If you see "Error loading data" in the admin interface, make sure LocalStack is running or your AWS credentials are configured correctly.

## API Examples

### Create a Category
```bash
curl -X POST http://localhost:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Electronics",
    "slug": "electronics",
    "description": "Electronic devices and accessories"
  }'
```

### Add a Product
```bash
curl -X POST http://localhost:8000/api/products/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Wireless Mouse",
    "slug": "wireless-mouse",
    "sku": "MOUSE-WL-001",
    "description": "Ergonomic wireless mouse with precision tracking",
    "price": 29.99,
    "compare_at_price": 39.99,
    "quantity": 100,
    "category_id": "cat-elec-123",
    "category_name": "Electronics",
    "tags": ["computer", "wireless", "accessories"],
    "brand": "TechBrand"
  }'
```

### Search Products
```bash
curl "http://localhost:8000/api/products/search/?q=wireless"
```

### Filter by Category
```bash
curl "http://localhost:8000/api/products/?category_id=cat-elec-123"
```

### Add a Review
```bash
curl -X POST http://localhost:8000/api/reviews/ \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "prod-123",
    "product_name": "Wireless Mouse",
    "user_id": "user-456",
    "user_name": "John Smith",
    "rating": 5,
    "title": "Great product!",
    "content": "Works perfectly, highly recommend",
    "verified_purchase": true
  }'
```

### Create an Order
```bash
curl -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -d '{
    "order_number": "ORD-2024-00001",
    "customer_id": "cust-123",
    "customer_email": "customer@example.com",
    "items": [
      {
        "product_id": "prod-123",
        "name": "Wireless Mouse",
        "quantity": 2,
        "price": 29.99
      }
    ],
    "subtotal": 59.98,
    "tax": 4.80,
    "shipping": 5.00,
    "total": 69.78
  }'
```

### Get Low Stock Products
```bash
curl http://localhost:8000/api/low-stock
```

## Workflows

### Product Management
1. Create categories
2. Add products with SKUs
3. Upload product images
4. Set pricing and inventory
5. Monitor stock levels

### Order Processing
1. Customer places order
2. Inventory is decremented
3. Order status tracked
4. Shipping information added
5. Customer notified

### Review Moderation
1. Customer submits review
2. Admin moderates (approve/reject)
3. Rating updates product
4. Helpful votes tracked

## Business Features

- **Sale Pricing**: Show compare_at_price for discounts
- **Low Stock Alerts**: Monitor inventory levels
- **SKU Management**: Unique product identifiers
- **Profit Tracking**: Track cost vs. price
- **Customer Analytics**: Track views and purchases
- **Review System**: Build trust with ratings

## Admin Interface

Visit http://localhost:8000/admin to:
- Manage products and inventory
- Process orders
- Moderate reviews
- Update categories
- View analytics

