# Disconnected Environment Setup Guide

This guide provides all necessary information to deploy the Server Scanner Dashboard in a disconnected (air-gapped) environment.

## Overview

This document contains:
1. **Complete list of container images** required
2. **Image download instructions** (from connected environment)
3. **Image transfer and upload instructions** (to disconnected registry)
4. **Helm chart configuration** for custom registries
5. **Verification steps**

---

## Container Images Required

### 1. Application Image

**Image**: Your custom-built application image

```bash
# Build from source
docker build -t server-scanner-dashboard:1.0.0 .
```

**Base Images Used During Build**:
- `python:3.11-slim` (builder stage)
- `python:3.11-slim` (runtime stage)

**Size**: ~200-250 MB (final image)

**Required for**: Main application deployment

---

### 2. PostgreSQL Database

**Image**: `postgres:15-alpine`

**Official Source**: Docker Hub - https://hub.docker.com/_/postgres

**Size**: ~234 MB

**Required for**: PostgreSQL database storage backend

**Alternative versions** (if needed):
- `postgres:15` (Debian-based, larger ~379 MB)
- `postgres:14-alpine` (older version)
- `postgres:16-alpine` (newer version)

---

## Complete Image List Summary

| Component | Image | Tag | Size | Registry |
|-----------|-------|-----|------|----------|
| **Application** | server-scanner-dashboard | 1.0.0 | ~230 MB | Custom build |
| **PostgreSQL** | postgres | 15-alpine | ~234 MB | docker.io |
| **Python Builder** | python | 3.11-slim | ~127 MB | docker.io (build only) |
| **Python Runtime** | python | 3.11-slim | ~127 MB | docker.io (build only) |

**Total Download Size**: ~724 MB (including build images)
**Runtime Images Only**: ~464 MB (application + postgres)

---

## Step 1: Download Images (Connected Environment)

### Download Script

Create a script to download all images:

```bash
#!/bin/bash
# download-images.sh

set -e

# Configuration
IMAGES=(
    "python:3.11-slim"
    "postgres:15-alpine"
)

OUTPUT_DIR="./docker-images"
mkdir -p "$OUTPUT_DIR"

echo "======================================"
echo "Downloading Container Images"
echo "======================================"
echo

# Pull and save each image
for image in "${IMAGES[@]}"; do
    echo "Processing: $image"

    # Pull image
    echo "  Pulling..."
    docker pull "$image"

    # Save to tar
    filename=$(echo "$image" | tr '/:' '_')
    echo "  Saving to ${filename}.tar..."
    docker save "$image" -o "${OUTPUT_DIR}/${filename}.tar"

    # Compress (optional but recommended)
    echo "  Compressing..."
    gzip "${OUTPUT_DIR}/${filename}.tar"

    echo "  ✓ Saved to ${OUTPUT_DIR}/${filename}.tar.gz"
    echo
done

echo "======================================"
echo "Building Application Image"
echo "======================================"
echo

# Build application image
APP_IMAGE="server-scanner-dashboard:1.0.0"
echo "Building $APP_IMAGE..."
docker build -t "$APP_IMAGE" .

# Save application image
echo "Saving application image..."
docker save "$APP_IMAGE" -o "${OUTPUT_DIR}/server-scanner-dashboard_1.0.0.tar"
gzip "${OUTPUT_DIR}/server-scanner-dashboard_1.0.0.tar"

echo
echo "======================================"
echo "Download Summary"
echo "======================================"
ls -lh "$OUTPUT_DIR"
echo
echo "Total size:"
du -sh "$OUTPUT_DIR"
echo
echo "Transfer the '$OUTPUT_DIR' directory to your disconnected environment"
echo "======================================"
```

### Execute Download

```bash
# Make executable
chmod +x download-images.sh

# Run download
./download-images.sh

# Verify downloads
ls -lh docker-images/
```

**Expected output**:
```
docker-images/
├── postgres_15-alpine.tar.gz           (~85 MB)
├── python_3.11-slim.tar.gz            (~45 MB)
├── server-scanner-dashboard_1.0.0.tar.gz  (~80 MB)
```

---

## Step 2: Transfer Images to Disconnected Environment

### Transfer Methods

#### Option A: Physical Media (USB/DVD)
```bash
# On connected system
tar -czf docker-images.tar.gz docker-images/

# Copy docker-images.tar.gz to USB drive
# Transfer to disconnected environment

# On disconnected system
tar -xzf docker-images.tar.gz
```

#### Option B: Secure File Transfer (if limited connectivity exists)
```bash
# Using SCP
scp -r docker-images/ user@disconnected-host:/tmp/

# Using rsync
rsync -avz docker-images/ user@disconnected-host:/tmp/docker-images/
```

---

## Step 3: Load Images (Disconnected Environment)

### Load Script

```bash
#!/bin/bash
# load-images.sh

set -e

IMAGE_DIR="./docker-images"

echo "======================================"
echo "Loading Container Images"
echo "======================================"
echo

# Load each tar.gz file
for tarball in "${IMAGE_DIR}"/*.tar.gz; do
    echo "Loading: $tarball"
    gunzip -c "$tarball" | docker load
    echo "  ✓ Loaded"
    echo
done

echo "======================================"
echo "Verifying Images"
echo "======================================"
docker images | grep -E "postgres|python|server-scanner"

echo
echo "✓ All images loaded successfully"
```

### Execute Load

```bash
chmod +x load-images.sh
./load-images.sh
```

---

## Step 4: Push to Private Registry

### Push Script

```bash
#!/bin/bash
# push-to-registry.sh

set -e

# Configuration - UPDATE THESE VALUES
PRIVATE_REGISTRY="your-registry.company.com"
PROJECT_NAME="server-scanner"

# Images to push
declare -A IMAGES=(
    ["postgres:15-alpine"]="${PRIVATE_REGISTRY}/${PROJECT_NAME}/postgres:15-alpine"
    ["server-scanner-dashboard:1.0.0"]="${PRIVATE_REGISTRY}/${PROJECT_NAME}/server-scanner-dashboard:1.0.0"
)

echo "======================================"
echo "Pushing Images to Private Registry"
echo "Registry: $PRIVATE_REGISTRY"
echo "======================================"
echo

# Login to private registry
echo "Logging in to registry..."
docker login "$PRIVATE_REGISTRY"

# Tag and push each image
for source in "${!IMAGES[@]}"; do
    target="${IMAGES[$source]}"

    echo "Processing: $source -> $target"

    # Tag image
    echo "  Tagging..."
    docker tag "$source" "$target"

    # Push image
    echo "  Pushing..."
    docker push "$target"

    echo "  ✓ Pushed successfully"
    echo
done

echo "======================================"
echo "Push Summary"
echo "======================================"
echo "All images pushed to: $PRIVATE_REGISTRY/$PROJECT_NAME/"
echo
echo "Images:"
for target in "${IMAGES[@]}"; do
    echo "  - $target"
done
echo "======================================"
```

### Execute Push

```bash
# Update registry configuration in script
vim push-to-registry.sh

# Run push
chmod +x push-to-registry.sh
./push-to-registry.sh
```

---

## Step 5: Configure Helm Chart for Private Registry

### Update values.yaml

```yaml
# Application image
image:
  repository: your-registry.company.com/server-scanner/server-scanner-dashboard
  pullPolicy: IfNotPresent
  tag: "1.0.0"

# PostgreSQL image
postgres:
  enabled: true
  image:
    repository: your-registry.company.com/server-scanner/postgres
    tag: "15-alpine"
    pullPolicy: IfNotPresent
  auth:
    username: scanner
    password: "YOUR_SECURE_PASSWORD"  # CHANGE THIS!
    database: server_scanner
  persistence:
    enabled: true
    size: 5Gi
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 256Mi

# Image pull secrets (if registry requires authentication)
imagePullSecrets:
  - name: registry-credentials
```

### Create Image Pull Secret (if needed)

```bash
# Create secret for private registry authentication
kubectl create secret docker-registry registry-credentials \
  --docker-server=your-registry.company.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  --docker-email=YOUR_EMAIL \
  --namespace=server-scanner
```

---

## Step 6: Deploy Application

### Deploy with Helm

```bash
# Create namespace
kubectl create namespace server-scanner

# Create image pull secret (if needed)
kubectl create secret docker-registry registry-credentials \
  --docker-server=your-registry.company.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  --namespace=server-scanner

# Install/upgrade with Helm
helm upgrade --install server-scanner-dashboard \
  ./deploy/helm/server-scanner-dashboard \
  --namespace server-scanner \
  --set image.repository=your-registry.company.com/server-scanner/server-scanner-dashboard \
  --set image.tag=1.0.0 \
  --set postgres.image.repository=your-registry.company.com/server-scanner/postgres \
  --set postgres.image.tag=15-alpine \
  --set postgres.auth.password=YOUR_SECURE_PASSWORD
```

---

## Step 7: Verification

### Verify Images

```bash
# Check application pod
kubectl get pods -n server-scanner -l app.kubernetes.io/name=server-scanner-dashboard

# Check PostgreSQL pod
kubectl get pods -n server-scanner -l app.kubernetes.io/component=database

# Verify images used
kubectl get pods -n server-scanner -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

Expected output:
```
server-scanner-dashboard-xxx    your-registry.company.com/server-scanner/server-scanner-dashboard:1.0.0
server-scanner-dashboard-postgres-0    your-registry.company.com/server-scanner/postgres:15-alpine
```

### Verify Application

```bash
# Check application logs
kubectl logs -n server-scanner -l app.kubernetes.io/name=server-scanner-dashboard --tail=50

# Check PostgreSQL logs
kubectl logs -n server-scanner -l app.kubernetes.io/component=database --tail=50

# Run verification script
./scripts/verify-postgres-setup.sh server-scanner
```

---

## Alternative: Using Quay/Harbor Registry

If you're using Quay or Harbor as your private registry:

### Quay.io

```bash
# Tag and push to Quay
docker tag server-scanner-dashboard:1.0.0 quay.io/your-org/server-scanner-dashboard:1.0.0
docker push quay.io/your-org/server-scanner-dashboard:1.0.0

docker tag postgres:15-alpine quay.io/your-org/postgres:15-alpine
docker push quay.io/your-org/postgres:15-alpine

# Update values.yaml
image:
  repository: quay.io/your-org/server-scanner-dashboard
postgres:
  image:
    repository: quay.io/your-org/postgres
```

### Harbor

```bash
# Tag and push to Harbor
docker tag server-scanner-dashboard:1.0.0 harbor.company.com/server-scanner/server-scanner-dashboard:1.0.0
docker push harbor.company.com/server-scanner/server-scanner-dashboard:1.0.0

docker tag postgres:15-alpine harbor.company.com/server-scanner/postgres:15-alpine
docker push harbor.company.com/server-scanner/postgres:15-alpine

# Update values.yaml
image:
  repository: harbor.company.com/server-scanner/server-scanner-dashboard
postgres:
  image:
    repository: harbor.company.com/server-scanner/postgres
```

---

## Troubleshooting

### Issue: ImagePullBackOff

```bash
# Check pod events
kubectl describe pod POD_NAME -n server-scanner

# Common causes:
# 1. Image doesn't exist in registry
docker pull your-registry.company.com/server-scanner/server-scanner-dashboard:1.0.0

# 2. Missing image pull secret
kubectl get secrets -n server-scanner | grep registry

# 3. Wrong image path
kubectl get pod POD_NAME -n server-scanner -o yaml | grep image:
```

### Issue: Registry Authentication Failed

```bash
# Test registry login
docker login your-registry.company.com

# Recreate pull secret
kubectl delete secret registry-credentials -n server-scanner
kubectl create secret docker-registry registry-credentials \
  --docker-server=your-registry.company.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  --namespace=server-scanner

# Verify secret
kubectl get secret registry-credentials -n server-scanner -o yaml
```

### Issue: Image Load Failed

```bash
# Check tar.gz integrity
gunzip -t docker-images/postgres_15-alpine.tar.gz

# Re-extract if needed
gunzip -c docker-images/postgres_15-alpine.tar.gz | docker load

# Verify loaded
docker images | grep postgres
```

---

## Size Optimization Tips

### 1. Use Alpine Images (Already Applied)
- PostgreSQL: `postgres:15-alpine` (234 MB vs 379 MB for debian)
- Application: `python:3.11-slim` (127 MB vs 1.01 GB for full python)

### 2. Multi-stage Builds (Already Applied)
- Build dependencies not included in final image
- Only runtime dependencies in final layer

### 3. Compress Transfers
- All tarballs are gzipped (typically 40-60% compression)
- Use `tar -czf` for directory transfer

### 4. Layer Caching
```bash
# When building, leverage layer caching
docker build --cache-from your-registry.company.com/server-scanner/server-scanner-dashboard:latest \
  -t server-scanner-dashboard:1.0.0 .
```

---

## Checklist

Before deploying in disconnected environment:

- [ ] Downloaded all required images from connected environment
- [ ] Compressed images for transfer (optional but recommended)
- [ ] Transferred images to disconnected environment
- [ ] Loaded images in disconnected environment
- [ ] Tagged images for private registry
- [ ] Pushed images to private registry
- [ ] Verified images in private registry
- [ ] Updated Helm values.yaml with private registry paths
- [ ] Created image pull secret (if needed)
- [ ] Deployed application with Helm
- [ ] Verified pods are running with correct images
- [ ] Tested application functionality

---

## Image Update Workflow

When updating to a new version:

```bash
# 1. Build new version (connected environment)
docker build -t server-scanner-dashboard:1.0.1 .

# 2. Save image
docker save server-scanner-dashboard:1.0.1 | gzip > server-scanner-dashboard_1.0.1.tar.gz

# 3. Transfer to disconnected environment
# ... (use your transfer method)

# 4. Load in disconnected environment
gunzip -c server-scanner-dashboard_1.0.1.tar.gz | docker load

# 5. Tag for private registry
docker tag server-scanner-dashboard:1.0.1 \
  your-registry.company.com/server-scanner/server-scanner-dashboard:1.0.1

# 6. Push to registry
docker push your-registry.company.com/server-scanner/server-scanner-dashboard:1.0.1

# 7. Update Helm deployment
helm upgrade server-scanner-dashboard \
  ./deploy/helm/server-scanner-dashboard \
  --namespace server-scanner \
  --set image.tag=1.0.1 \
  --reuse-values
```

---

## Security Considerations

### Registry Security

1. **TLS/SSL**: Ensure private registry uses HTTPS
2. **Authentication**: Use strong credentials for registry access
3. **RBAC**: Limit registry access to authorized users
4. **Image Scanning**: Scan images for vulnerabilities before pushing

### Kubernetes Security

1. **Image Pull Secrets**: Use secrets for registry authentication
2. **Pod Security**: Apply security contexts (already configured)
3. **Network Policies**: Restrict pod-to-pod communication
4. **RBAC**: Limit service account permissions

---

## Summary

**What you need to download** (from internet-connected environment):
1. `python:3.11-slim` (~127 MB) - For building application
2. `postgres:15-alpine` (~234 MB) - PostgreSQL database
3. Your built application image (~230 MB)

**Total download**: ~464 MB (runtime images only)

**Process**:
1. Download images → 2. Transfer → 3. Load → 4. Push to registry → 5. Deploy

**Key Files**:
- `download-images.sh` - Download script for connected environment
- `load-images.sh` - Load script for disconnected environment
- `push-to-registry.sh` - Push script for private registry
- `values.yaml` - Update with your registry paths

For questions or issues, refer to the troubleshooting section or check the deployment logs.
