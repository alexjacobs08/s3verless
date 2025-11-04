#!/bin/bash
# Quick start script for S3verless examples

echo "🚀 S3verless Examples Quick Start"
echo ""

# Check if example argument provided
if [ -z "$1" ]; then
    echo "Usage: ./quickstart.sh [example_name]"
    echo ""
    echo "Available examples:"
    echo "  - todo_app        : Simple todo list (beginner)"
    echo "  - blog_platform   : Blog with ownership & admin (advanced)"
    echo "  - ecommerce       : Product catalog (intermediate)"
    echo "  - auth_example    : JWT authentication basics (intermediate)"
    echo ""
    echo "Example: ./quickstart.sh todo_app"
    exit 1
fi

EXAMPLE=$1
EXAMPLE_DIR="${EXAMPLE}"

# Check if example exists
if [ ! -d "$EXAMPLE_DIR" ]; then
    echo "❌ Example '$EXAMPLE' not found!"
    echo "Available examples: todo_app, blog_platform, ecommerce, auth_example"
    exit 1
fi

echo "📦 Setting up $EXAMPLE..."
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your AWS credentials!"
    echo ""
    read -p "Press Enter to continue after updating .env..."
fi

# Install dependencies
echo "📥 Installing dependencies..."
if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt
else
    echo "⚠️  uv not found, using pip (install uv for faster installs: curl -LsSf https://astral.sh/uv/install.sh | sh)"
    pip install -q -r requirements.txt
fi

# Check if LocalStack is preferred
read -p "🐳 Use LocalStack for local development? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting LocalStack..."
    echo "Make sure you have Docker running!"
    
    # Check if localstack is running
    if ! docker ps | grep -q localstack; then
        echo "Starting LocalStack container..."
        localstack start -d
        echo "⏳ Waiting for LocalStack to be ready..."
        sleep 10
    fi
    
    # Update .env to use LocalStack
    export AWS_URL=http://localhost:4566
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
    
    echo "✅ LocalStack ready at http://localhost:4566"
fi

echo ""
echo "🎯 Starting $EXAMPLE..."
echo "📍 API will be available at: http://localhost:8000"
echo "📖 API docs at: http://localhost:8000/docs"
echo "🎨 Admin interface at: http://localhost:8000/admin"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the example
cd "$EXAMPLE_DIR" || exit 1
python main.py

