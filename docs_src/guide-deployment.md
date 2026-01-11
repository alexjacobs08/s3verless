# Deployment Guide

Deploy S3verless applications to AWS Lambda, Docker, or with LocalStack for development.

## AWS Lambda with Mangum

### Setup

Install dependencies:

```bash
pip install mangum
```

### Lambda Handler

```python
# main.py
from mangum import Mangum
from s3verless.fastapi.app import S3verless
from s3verless.core.settings import S3verlessSettings

settings = S3verlessSettings()

app_builder = S3verless(
    settings=settings,
    title="My API",
    model_packages=["models"],
)

app = app_builder.create_app()
handler = Mangum(app)
```

### Serverless Framework

```yaml
# serverless.yml
service: my-s3verless-api

provider:
  name: aws
  runtime: python3.12
  region: us-east-1
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - s3:GetObject
            - s3:PutObject
            - s3:DeleteObject
            - s3:ListBucket
            - s3:HeadBucket
            - s3:CreateBucket
          Resource:
            - arn:aws:s3:::${self:custom.bucketName}
            - arn:aws:s3:::${self:custom.bucketName}/*

  environment:
    AWS_BUCKET_NAME: ${self:custom.bucketName}
    SECRET_KEY: ${ssm:/my-api/secret-key}

custom:
  bucketName: my-s3verless-data-${self:provider.stage}

functions:
  api:
    handler: main.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
      - http:
          path: /
          method: ANY

resources:
  Resources:
    DataBucket:
      Type: AWS::S3::Bucket
      Properties:
        BucketName: ${self:custom.bucketName}
```

Deploy:

```bash
serverless deploy
```

### SAM Template

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    MemorySize: 256

Parameters:
  SecretKey:
    Type: String
    NoEcho: true

Resources:
  DataBucket:
    Type: AWS::S3::Bucket

  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.12
      CodeUri: .
      Environment:
        Variables:
          AWS_BUCKET_NAME: !Ref DataBucket
          SECRET_KEY: !Ref SecretKey
      Policies:
        - S3CrudPolicy:
            BucketName: !Ref DataBucket
      Events:
        Api:
          Type: Api
          Properties:
            Path: /{proxy+}
            Method: ANY

Outputs:
  ApiUrl:
    Value: !Sub https://${ServerlessRestApi}.execute-api.${AWS::Region}.amazonaws.com/Prod/
```

Deploy:

```bash
sam build
sam deploy --guided
```

## Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=us-east-1
      - AWS_BUCKET_NAME=${AWS_BUCKET_NAME}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - localstack

  localstack:
    image: localstack/localstack
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3
      - DEBUG=1
```

### Production Docker

```dockerfile
FROM python:3.12-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## LocalStack for Development

### Setup

```bash
docker run -d -p 4566:4566 localstack/localstack
```

### Configuration

```python
# .env.local
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_BUCKET_NAME=local-bucket
AWS_REGION=us-east-1
```

### Initialize Bucket

```python
# scripts/init_localstack.py
import asyncio
import aiobotocore.session

async def init():
    session = aiobotocore.session.get_session()
    async with session.create_client(
        's3',
        endpoint_url='http://localhost:4566',
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
    ) as s3:
        try:
            await s3.create_bucket(Bucket='local-bucket')
            print("Bucket created")
        except Exception as e:
            print(f"Bucket exists or error: {e}")

if __name__ == "__main__":
    asyncio.run(init())
```

## Environment Configuration

### Production Checklist

```bash
# Required
AWS_BUCKET_NAME=prod-data-bucket
SECRET_KEY=$(openssl rand -hex 32)  # Generate secure key

# AWS (if not using IAM roles)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Optional
S3_BASE_PATH=data/
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Admin (optional)
CREATE_DEFAULT_ADMIN=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=...  # Use secrets manager
DEFAULT_ADMIN_EMAIL=admin@example.com
```

### AWS Secrets Manager

```python
import boto3
import json

def get_secrets():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='my-api/secrets')
    return json.loads(response['SecretString'])

# In settings
secrets = get_secrets()
settings = S3verlessSettings(
    secret_key=secrets['SECRET_KEY'],
    # ...
)
```

## Performance Optimization

### Lambda Cold Starts

```python
# Keep connections warm
from s3verless.core.client import S3ClientManager

# Initialize outside handler
manager = S3ClientManager(settings)

def handler(event, context):
    # Manager is reused across invocations
    pass
```

### Memory Settings

- **Lambda**: Start with 256MB, increase if needed
- **Docker**: Set memory limits based on expected load
- Monitor with CloudWatch/Prometheus

### Connection Pooling

```python
from s3verless.core.client import PoolConfig

pool_config = PoolConfig(
    max_connections=10,
    connection_timeout=5.0,
)
manager = S3ClientManager(settings, pool_config)
```

## Monitoring

### CloudWatch Logs

Lambda logs automatically to CloudWatch. Add structured logging:

```python
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_request(event):
    logger.info(json.dumps({
        "type": "request",
        "path": event.get("path"),
        "method": event.get("httpMethod"),
    }))
```

### Health Check

```python
@app.get("/health")
async def health():
    try:
        async with s3_manager.get_async_client() as s3:
            await s3.head_bucket(Bucket=bucket_name)
        return {"status": "healthy", "s3": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Security

### IAM Policy (Least Privilege)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::my-bucket/data/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::my-bucket",
      "Condition": {
        "StringLike": {"s3:prefix": ["data/*"]}
      }
    }
  ]
}
```

### S3 Bucket Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnencryptedUploads",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::my-bucket/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

### Enable Encryption

```python
# S3 bucket encryption (set via AWS Console or CloudFormation)
# Or encrypt in application:
await s3_client.put_object(
    Bucket=bucket,
    Key=key,
    Body=data,
    ServerSideEncryption='AES256',
)
```

## CI/CD

### GitHub Actions

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest

      - name: Deploy to Lambda
        uses: serverless/github-action@v3
        with:
          args: deploy
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```
