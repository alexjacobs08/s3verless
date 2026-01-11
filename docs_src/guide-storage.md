# File Storage Guide

Handle file uploads with presigned URLs for direct S3 uploads.

## Overview

S3verless provides presigned URL functionality that lets clients upload files directly to S3, bypassing your server. This reduces bandwidth, latency, and server load.

## Setup

### Configure Upload Service

```python
from s3verless.storage.uploads import PresignedUploadService, UploadConfig

config = UploadConfig(
    max_file_size=10 * 1024 * 1024,  # 10MB
    allowed_content_types=["image/jpeg", "image/png", "application/pdf"],
    upload_prefix="uploads/",
    expiration_seconds=3600,  # 1 hour
)

upload_service = PresignedUploadService("my-bucket", config)
```

## Upload Flow

### 1. Generate Upload URL

```python
# Server generates presigned URL
url_data = await upload_service.generate_upload_url(
    s3_client,
    filename="photo.jpg",
    content_type="image/jpeg",
    metadata={"uploaded_by": str(user.id)},
)

# Returns:
# {
#     "url": "https://bucket.s3.amazonaws.com",
#     "key": "uploads/2024/01/15/abc123.jpg",
#     "fields": {"key": "...", "Content-Type": "...", ...},
#     "expires_in": 3600,
#     "max_size": 10485760,
# }
```

### 2. Client Uploads to S3

Client uses the presigned URL to upload directly:

```javascript
// JavaScript client
const formData = new FormData();

// Add all fields from the response
Object.entries(urlData.fields).forEach(([key, value]) => {
    formData.append(key, value);
});

// Add the file last
formData.append('file', file);

// POST to the presigned URL
await fetch(urlData.url, {
    method: 'POST',
    body: formData,
});
```

### 3. Confirm Upload

After upload, confirm and create a record:

```python
# Server confirms the upload
file_record = await upload_service.confirm_upload(
    s3_client,
    s3_key=url_data["key"],
    uploaded_by=user.id,
)

if file_record:
    # Upload confirmed, file_record contains metadata
    print(f"Uploaded: {file_record.filename}, {file_record.size} bytes")
else:
    # Upload failed or not found
    print("Upload not found")
```

## Download URLs

Generate presigned download URLs:

```python
download_url = await upload_service.generate_download_url(
    s3_client,
    s3_key="uploads/2024/01/15/abc123.jpg",
    filename="my-photo.jpg",  # Suggested download name
    expires_in=3600,
)
# https://bucket.s3.amazonaws.com/uploads/...?...
```

## Delete Files

```python
deleted = await upload_service.delete_file(s3_client, s3_key)
if deleted:
    print("File deleted")
```

## FastAPI Integration

### Upload Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/files", tags=["files"])

class UploadRequest(BaseModel):
    filename: str
    content_type: str | None = None

class UploadResponse(BaseModel):
    url: str
    key: str
    fields: dict
    expires_in: int

@router.post("/upload-url", response_model=UploadResponse)
async def get_upload_url(
    request: UploadRequest,
    s3_client = Depends(get_s3_client),
    user = Depends(get_current_user),
):
    try:
        data = await upload_service.generate_upload_url(
            s3_client,
            filename=request.filename,
            content_type=request.content_type,
            metadata={"user_id": str(user.id)},
        )
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/confirm/{key:path}")
async def confirm_upload(
    key: str,
    s3_client = Depends(get_s3_client),
    user = Depends(get_current_user),
):
    file_record = await upload_service.confirm_upload(
        s3_client, key, uploaded_by=user.id
    )
    if not file_record:
        raise HTTPException(404, "Upload not found")
    return {"file_id": str(file_record.id), "filename": file_record.filename}

@router.get("/download/{file_id}")
async def get_download_url(
    file_id: str,
    s3_client = Depends(get_s3_client),
):
    # Get file record
    file_service = S3DataService(UploadedFile, bucket)
    file_record = await file_service.get(s3_client, UUID(file_id))
    if not file_record:
        raise HTTPException(404, "File not found")

    url = await upload_service.generate_download_url(
        s3_client,
        s3_key=file_record.s3_key,
        filename=file_record.filename,
    )
    return {"download_url": url}
```

## Content Type Validation

Restrict allowed file types:

```python
config = UploadConfig(
    allowed_content_types=[
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
    ],
)
```

Attempting to upload a disallowed type raises `ValueError`.

## File Size Limits

```python
config = UploadConfig(
    max_file_size=50 * 1024 * 1024,  # 50MB
)
```

S3 enforces this via presigned POST conditions.

## Organizing Uploads

Files are organized by date:

```
bucket/
└── uploads/
    └── 2024/
        └── 01/
            └── 15/
                ├── abc123.jpg
                └── def456.pdf
```

Custom organization:

```python
# Override key generation
class CustomUploadService(PresignedUploadService):
    def _generate_key(self, filename: str) -> str:
        file_id = uuid.uuid4()
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return f"files/{file_id}{ext}"
```

## Linking Files to Models

### File Reference Field

```python
class Product(BaseS3Model):
    name: str
    image_id: UUID | None = None  # Reference to UploadedFile
```

### With Image URL

```python
@router.get("/products/{product_id}")
async def get_product(product_id: str, s3_client = Depends(get_s3_client)):
    product = await product_service.get(s3_client, UUID(product_id))

    response = product.model_dump()

    if product.image_id:
        file_record = await file_service.get(s3_client, product.image_id)
        if file_record:
            response["image_url"] = await upload_service.generate_download_url(
                s3_client, file_record.s3_key, expires_in=3600
            )

    return response
```

## Image Processing

For image processing, consider AWS Lambda triggers:

```python
# Lambda function triggered on S3 upload
def process_image(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    # Download, resize, create thumbnails
    # Upload processed versions
```

## Security Considerations

1. **Validate content types** - Use `allowed_content_types`
2. **Limit file sizes** - Use `max_file_size`
3. **Short expiry** - Keep presigned URLs short-lived
4. **Scan uploads** - Consider virus scanning for user uploads
5. **Private by default** - Files are private unless explicitly shared
6. **User ownership** - Track `uploaded_by` for access control

## Best Practices

1. **Use presigned URLs** - Don't proxy files through your server
2. **Confirm uploads** - Verify file exists before creating records
3. **Handle failures** - Client upload may fail, check before assuming success
4. **Organize files** - Use date-based or user-based prefixes
5. **Clean up orphans** - Periodically delete unconfirmed uploads
6. **Set appropriate TTLs** - Balance security vs. convenience
