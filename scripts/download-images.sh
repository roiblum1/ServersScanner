#!/bin/bash
#
# Download Container Images for Disconnected Environment
#
# This script downloads all required container images and prepares them
# for transfer to a disconnected environment.
#
# Usage:
#   ./download-images.sh [output-directory]
#
# Example:
#   ./download-images.sh ./docker-images
#

set -e

# Configuration
OUTPUT_DIR="${1:-./docker-images}"
APP_VERSION="1.0.0"

# Images to download
IMAGES=(
    "python:3.11-slim"
    "postgres:15-alpine"
)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Container Image Download Script"
echo "======================================"
echo "Output directory: $OUTPUT_DIR"
echo "Application version: $APP_VERSION"
echo "======================================"
echo

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to save image
save_image() {
    local image=$1
    local filename=$(echo "$image" | tr '/:' '_')

    echo -e "${GREEN}Processing: $image${NC}"

    # Pull image
    echo "  [1/3] Pulling image..."
    if docker pull "$image"; then
        echo "        ✓ Pulled successfully"
    else
        echo "        ✗ Failed to pull image"
        return 1
    fi

    # Save to tar
    echo "  [2/3] Saving to tar..."
    if docker save "$image" -o "${OUTPUT_DIR}/${filename}.tar"; then
        local size=$(du -h "${OUTPUT_DIR}/${filename}.tar" | cut -f1)
        echo "        ✓ Saved (size: $size)"
    else
        echo "        ✗ Failed to save image"
        return 1
    fi

    # Compress
    echo "  [3/3] Compressing..."
    if gzip -f "${OUTPUT_DIR}/${filename}.tar"; then
        local compressed_size=$(du -h "${OUTPUT_DIR}/${filename}.tar.gz" | cut -f1)
        echo "        ✓ Compressed (size: $compressed_size)"
    else
        echo "        ✗ Failed to compress"
        return 1
    fi

    echo
    return 0
}

# Download each image
echo "Downloading base images..."
echo
for image in "${IMAGES[@]}"; do
    save_image "$image"
done

# Build application image
echo "======================================"
echo "Building Application Image"
echo "======================================"
echo

APP_IMAGE="server-scanner-dashboard:${APP_VERSION}"

if [ -f "Dockerfile" ]; then
    echo "Building $APP_IMAGE..."
    if docker build -t "$APP_IMAGE" .; then
        echo "✓ Build successful"
        echo

        # Save application image
        echo "Saving application image..."
        filename="server-scanner-dashboard_${APP_VERSION}"

        docker save "$APP_IMAGE" -o "${OUTPUT_DIR}/${filename}.tar"
        local size=$(du -h "${OUTPUT_DIR}/${filename}.tar" | cut -f1)
        echo "  ✓ Saved (size: $size)"

        gzip -f "${OUTPUT_DIR}/${filename}.tar"
        local compressed_size=$(du -h "${OUTPUT_DIR}/${filename}.tar.gz" | cut -f1)
        echo "  ✓ Compressed (size: $compressed_size)"
    else
        echo "✗ Build failed"
        echo "Make sure you run this script from the project root directory"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Dockerfile not found in current directory${NC}"
    echo "Skipping application image build"
    echo "Make sure to build it separately: docker build -t $APP_IMAGE ."
fi

echo
echo "======================================"
echo "Download Summary"
echo "======================================"
echo
echo "Files in $OUTPUT_DIR:"
ls -lh "$OUTPUT_DIR" | tail -n +2
echo
echo "Total size:"
du -sh "$OUTPUT_DIR"
echo
echo "======================================"
echo "✓ Download Complete"
echo "======================================"
echo
echo "Next steps:"
echo "  1. Transfer the '$OUTPUT_DIR' directory to your disconnected environment"
echo "  2. Run ./load-images.sh in the disconnected environment"
echo "  3. Push images to your private registry with ./push-to-registry.sh"
echo
