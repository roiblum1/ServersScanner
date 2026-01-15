#!/bin/bash
#
# Push Container Images to Private Registry
#
# This script tags and pushes container images to a private registry
# for use in a disconnected environment.
#
# Usage:
#   REGISTRY=your-registry.com PROJECT=server-scanner ./push-to-registry.sh
#
# Example:
#   REGISTRY=harbor.company.com PROJECT=apps ./push-to-registry.sh
#

set -e

# Configuration - can be overridden by environment variables
PRIVATE_REGISTRY="${REGISTRY:-your-registry.company.com}"
PROJECT_NAME="${PROJECT:-server-scanner}"
APP_VERSION="${VERSION:-1.0.0}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "======================================"
echo "Push Images to Private Registry"
echo "======================================"
echo "Registry: $PRIVATE_REGISTRY"
echo "Project: $PROJECT_NAME"
echo "App Version: $APP_VERSION"
echo "======================================"
echo

# Check if registry is configured
if [ "$PRIVATE_REGISTRY" == "your-registry.company.com" ]; then
    echo -e "${YELLOW}⚠ Warning: Using default registry URL${NC}"
    echo
    echo "Please set your registry:"
    echo "  export REGISTRY=your-registry.company.com"
    echo "  export PROJECT=server-scanner"
    echo "  $0"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Define source -> target mappings
declare -A IMAGES=(
    ["postgres:15-alpine"]="${PRIVATE_REGISTRY}/${PROJECT_NAME}/postgres:15-alpine"
    ["server-scanner-dashboard:${APP_VERSION}"]="${PRIVATE_REGISTRY}/${PROJECT_NAME}/server-scanner-dashboard:${APP_VERSION}"
)

# Optional: Python base image (only needed if you want to cache it in your registry)
# Uncomment if you want to include it
# IMAGES["python:3.11-slim"]="${PRIVATE_REGISTRY}/${PROJECT_NAME}/python:3.11-slim"

echo "Images to push:"
for source in "${!IMAGES[@]}"; do
    target="${IMAGES[$source]}"
    echo "  $source -> $target"
done
echo

# Login to private registry
echo "======================================"
echo "Registry Login"
echo "======================================"
echo "Logging in to: $PRIVATE_REGISTRY"
echo

if docker login "$PRIVATE_REGISTRY"; then
    echo -e "${GREEN}✓ Login successful${NC}"
else
    echo -e "${RED}✗ Login failed${NC}"
    echo "Please check your credentials and try again"
    exit 1
fi

echo

# Tag and push each image
echo "======================================"
echo "Pushing Images"
echo "======================================"
echo

success_count=0
failed_count=0

for source in "${!IMAGES[@]}"; do
    target="${IMAGES[$source]}"

    echo -e "${GREEN}Processing: $source${NC}"

    # Check if source image exists
    if ! docker image inspect "$source" &> /dev/null; then
        echo -e "  ${RED}✗ Source image not found: $source${NC}"
        echo "    Please load the image first with: docker load < image.tar"
        ((failed_count++))
        echo
        continue
    fi

    # Tag image
    echo "  [1/2] Tagging as: $target"
    if docker tag "$source" "$target"; then
        echo "        ✓ Tagged"
    else
        echo -e "        ${RED}✗ Failed to tag${NC}"
        ((failed_count++))
        echo
        continue
    fi

    # Push image
    echo "  [2/2] Pushing to registry..."
    if docker push "$target"; then
        echo -e "        ${GREEN}✓ Pushed successfully${NC}"
        ((success_count++))
    else
        echo -e "        ${RED}✗ Failed to push${NC}"
        ((failed_count++))
    fi

    echo
done

echo "======================================"
echo "Push Summary"
echo "======================================"
echo "  Successfully pushed: $success_count"
echo "  Failed: $failed_count"
echo "======================================"
echo

if [ $failed_count -eq 0 ]; then
    echo -e "${GREEN}✓ All images pushed successfully${NC}"
    echo
    echo "Images are now available at:"
    for target in "${IMAGES[@]}"; do
        echo "  - $target"
    done
    echo
    echo "======================================"
    echo "Next Steps"
    echo "======================================"
    echo "1. Update your Helm values.yaml:"
    echo
    cat << EOF
   image:
     repository: ${PRIVATE_REGISTRY}/${PROJECT_NAME}/server-scanner-dashboard
     tag: "${APP_VERSION}"

   postgres:
     image:
       repository: ${PRIVATE_REGISTRY}/${PROJECT_NAME}/postgres
       tag: "15-alpine"
EOF
    echo
    echo "2. Create image pull secret (if needed):"
    echo
    echo "   kubectl create secret docker-registry registry-credentials \\"
    echo "     --docker-server=${PRIVATE_REGISTRY} \\"
    echo "     --docker-username=YOUR_USERNAME \\"
    echo "     --docker-password=YOUR_PASSWORD \\"
    echo "     --namespace=server-scanner"
    echo
    echo "3. Deploy with Helm:"
    echo
    echo "   helm upgrade --install server-scanner-dashboard \\"
    echo "     ./deploy/helm/server-scanner-dashboard \\"
    echo "     --namespace server-scanner \\"
    echo "     --set postgres.auth.password=YOUR_PASSWORD"
    echo
else
    echo -e "${RED}⚠ Some images failed to push${NC}"
    echo "Please check the errors above and try again"
    echo
fi
