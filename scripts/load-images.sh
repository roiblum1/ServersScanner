#!/bin/bash
#
# Load Container Images in Disconnected Environment
#
# This script loads container images from tar.gz files into the local
# Docker daemon.
#
# Usage:
#   ./load-images.sh [image-directory]
#
# Example:
#   ./load-images.sh ./docker-images
#

set -e

# Configuration
IMAGE_DIR="${1:-./docker-images}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "======================================"
echo "Container Image Load Script"
echo "======================================"
echo "Image directory: $IMAGE_DIR"
echo "======================================"
echo

# Check if directory exists
if [ ! -d "$IMAGE_DIR" ]; then
    echo -e "${RED}✗ Directory not found: $IMAGE_DIR${NC}"
    echo "Please provide the correct path to the image directory"
    exit 1
fi

# Check if directory has any tar.gz files
if ! ls "$IMAGE_DIR"/*.tar.gz 1> /dev/null 2>&1; then
    echo -e "${RED}✗ No .tar.gz files found in $IMAGE_DIR${NC}"
    echo "Please ensure the image files are in the correct directory"
    exit 1
fi

# Load each tar.gz file
loaded_count=0
failed_count=0

for tarball in "$IMAGE_DIR"/*.tar.gz; do
    filename=$(basename "$tarball")
    echo -e "${GREEN}Loading: $filename${NC}"

    if gunzip -c "$tarball" | docker load; then
        echo "  ✓ Loaded successfully"
        ((loaded_count++))
    else
        echo -e "  ${RED}✗ Failed to load${NC}"
        ((failed_count++))
    fi
    echo
done

echo "======================================"
echo "Load Summary"
echo "======================================"
echo "  Successfully loaded: $loaded_count"
echo "  Failed: $failed_count"
echo "======================================"
echo

# Verify images
echo "Verifying loaded images..."
echo "======================================"
echo
echo "PostgreSQL images:"
docker images | head -n 1
docker images | grep -E "postgres" || echo "No PostgreSQL images found"
echo
echo "Python images:"
docker images | grep -E "python" || echo "No Python images found"
echo
echo "Application images:"
docker images | grep -E "server-scanner" || echo "No application images found"
echo

if [ $failed_count -eq 0 ]; then
    echo "======================================"
    echo "✓ All images loaded successfully"
    echo "======================================"
    echo
    echo "Next steps:"
    echo "  1. Push images to your private registry: ./push-to-registry.sh"
    echo "  2. Update Helm values.yaml with your registry paths"
    echo "  3. Deploy with Helm"
    echo
else
    echo "======================================"
    echo "⚠ Some images failed to load"
    echo "======================================"
    echo
    echo "Please check the errors above and try again"
    echo
fi
