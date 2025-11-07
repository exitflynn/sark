#!/bin/bash
# Push Sark to Docker Hub

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║      Sark - Docker Hub Push                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "✗ Docker is not running. Please start Docker Desktop."
    exit 1
fi
echo "✓ Docker is running"

# Get Docker Hub username
echo ""
read -p "Enter your Docker Hub username: " DOCKERHUB_USER

if [ -z "$DOCKERHUB_USER" ]; then
    echo "✗ Username cannot be empty"
    exit 1
fi

# Get version tag (optional)
echo ""
read -p "Enter version tag (default: latest): " VERSION
VERSION=${VERSION:-latest}

IMAGE_NAME="sark"
FULL_IMAGE="$DOCKERHUB_USER/$IMAGE_NAME:$VERSION"

echo ""
echo "▶ Building image..."
docker build -t $IMAGE_NAME:latest .
echo "  ✓ Image built: $IMAGE_NAME:latest"

echo ""
echo "▶ Tagging image..."
docker tag $IMAGE_NAME:latest $FULL_IMAGE
if [ "$VERSION" != "latest" ]; then
    docker tag $IMAGE_NAME:latest $DOCKERHUB_USER/$IMAGE_NAME:latest
    echo "  ✓ Tagged: $FULL_IMAGE"
    echo "  ✓ Tagged: $DOCKERHUB_USER/$IMAGE_NAME:latest"
else
    echo "  ✓ Tagged: $FULL_IMAGE"
fi

echo ""
echo "▶ Pushing to Docker Hub..."
docker push $FULL_IMAGE
if [ "$VERSION" != "latest" ]; then
    docker push $DOCKERHUB_USER/$IMAGE_NAME:latest
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  Push Successful! ✓                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Image pushed to: $FULL_IMAGE"
if [ "$VERSION" != "latest" ]; then
    echo "Also tagged as: $DOCKERHUB_USER/$IMAGE_NAME:latest"
fi
echo ""
echo "To pull on EC2:"
echo "  docker pull $FULL_IMAGE"
echo ""
echo "To run:"
echo "  docker run -d --name sark --restart unless-stopped \\
echo "    -p 5000:5000 -p 6379:6379 \\
echo "    $FULL_IMAGE"
echo ""
