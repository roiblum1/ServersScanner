# Container Images Quick Reference

## Images Required for Disconnected Environment

### Runtime Images (Required for Deployment)

| Image | Full Name | Size (Compressed) | Purpose |
|-------|-----------|-------------------|---------|
| **PostgreSQL** | `postgres:15-alpine` | ~85 MB | Database storage backend |
| **Application** | `server-scanner-dashboard:1.0.0` | ~80 MB | Main application |

**Total Runtime Download**: ~165 MB (compressed)

---

### Build Images (Required for Building Application)

| Image | Full Name | Size (Compressed) | Purpose |
|-------|-----------|-------------------|---------|
| **Python Base** | `python:3.11-slim` | ~45 MB | Application build base |

**Total Build Download**: ~45 MB (compressed)

---

## Download Commands (Connected Environment)

```bash
# 1. Pull PostgreSQL
docker pull postgres:15-alpine

# 2. Pull Python (for building)
docker pull python:3.11-slim

# 3. Build application
docker build -t server-scanner-dashboard:1.0.0 .

# 4. Save all images
docker save postgres:15-alpine | gzip > postgres_15-alpine.tar.gz
docker save python:3.11-slim | gzip > python_3.11-slim.tar.gz
docker save server-scanner-dashboard:1.0.0 | gzip > server-scanner-dashboard_1.0.0.tar.gz
```

**Or use the automated script:**
```bash
./scripts/download-images.sh
```

---

## Load Commands (Disconnected Environment)

```bash
# Load each image
gunzip -c postgres_15-alpine.tar.gz | docker load
gunzip -c server-scanner-dashboard_1.0.0.tar.gz | docker load

# Verify
docker images | grep -E "postgres|server-scanner"
```

**Or use the automated script:**
```bash
./scripts/load-images.sh ./docker-images
```

---

## Push to Registry (Disconnected Environment)

```bash
# Configure registry
export REGISTRY=your-registry.company.com
export PROJECT=server-scanner

# Tag images
docker tag postgres:15-alpine $REGISTRY/$PROJECT/postgres:15-alpine
docker tag server-scanner-dashboard:1.0.0 $REGISTRY/$PROJECT/server-scanner-dashboard:1.0.0

# Login and push
docker login $REGISTRY
docker push $REGISTRY/$PROJECT/postgres:15-alpine
docker push $REGISTRY/$PROJECT/server-scanner-dashboard:1.0.0
```

**Or use the automated script:**
```bash
REGISTRY=your-registry.com PROJECT=server-scanner ./scripts/push-to-registry.sh
```

---

## Helm Configuration

Update `values.yaml` with your registry paths:

```yaml
image:
  repository: your-registry.company.com/server-scanner/server-scanner-dashboard
  tag: "1.0.0"

postgres:
  enabled: true
  image:
    repository: your-registry.company.com/server-scanner/postgres
    tag: "15-alpine"
  auth:
    password: "YOUR_SECURE_PASSWORD"
```

---

## Image Pull Secret (If Required)

```bash
kubectl create secret docker-registry registry-credentials \
  --docker-server=your-registry.company.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  --namespace=server-scanner
```

Add to `values.yaml`:
```yaml
imagePullSecrets:
  - name: registry-credentials
```

---

## Verification Commands

```bash
# Check images in registry
curl -u USERNAME:PASSWORD https://your-registry.company.com/v2/_catalog

# Check deployed pods
kubectl get pods -n server-scanner -o wide

# Check images used by pods
kubectl get pods -n server-scanner -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

---

## Size Summary

| Component | Uncompressed | Compressed | Type |
|-----------|-------------|------------|------|
| PostgreSQL 15 Alpine | ~234 MB | ~85 MB | Runtime |
| Python 3.11 Slim | ~127 MB | ~45 MB | Build |
| Application | ~230 MB | ~80 MB | Runtime |
| **Runtime Total** | **~464 MB** | **~165 MB** | - |
| **With Build** | **~591 MB** | **~210 MB** | - |

---

## Transfer Methods

### Option 1: USB Drive
```bash
# On connected system
tar -czf images-bundle.tar.gz docker-images/
# Copy to USB, transfer to disconnected system

# On disconnected system
tar -xzf images-bundle.tar.gz
cd docker-images
```

### Option 2: Network (if limited connectivity)
```bash
# Using SCP
scp -r docker-images/ user@disconnected-host:/tmp/

# Using rsync
rsync -avz docker-images/ user@disconnected-host:/tmp/docker-images/
```

---

## Alternative Registry Examples

### Using Quay.io
```bash
docker tag server-scanner-dashboard:1.0.0 quay.io/your-org/server-scanner-dashboard:1.0.0
docker push quay.io/your-org/server-scanner-dashboard:1.0.0
```

**values.yaml:**
```yaml
image:
  repository: quay.io/your-org/server-scanner-dashboard
```

### Using Harbor
```bash
docker tag server-scanner-dashboard:1.0.0 harbor.company.com/server-scanner/server-scanner-dashboard:1.0.0
docker push harbor.company.com/server-scanner/server-scanner-dashboard:1.0.0
```

**values.yaml:**
```yaml
image:
  repository: harbor.company.com/server-scanner/server-scanner-dashboard
```

### Using Artifactory
```bash
docker tag server-scanner-dashboard:1.0.0 artifactory.company.com/docker/server-scanner-dashboard:1.0.0
docker push artifactory.company.com/docker/server-scanner-dashboard:1.0.0
```

**values.yaml:**
```yaml
image:
  repository: artifactory.company.com/docker/server-scanner-dashboard
```

---

## Troubleshooting

### ImagePullBackOff
```bash
# Check pod details
kubectl describe pod POD_NAME -n server-scanner

# Common fixes:
# 1. Verify image exists in registry
# 2. Check image pull secret
# 3. Verify image path is correct
```

### Authentication Failed
```bash
# Test registry login
docker login your-registry.company.com

# Recreate secret
kubectl delete secret registry-credentials -n server-scanner
kubectl create secret docker-registry registry-credentials \
  --docker-server=your-registry.company.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  --namespace=server-scanner
```

### Image Not Found
```bash
# List images in Docker
docker images

# List images in registry (if API available)
curl -u USER:PASS https://registry.com/v2/PROJECT/server-scanner-dashboard/tags/list
```

---

## Checklist

**Connected Environment:**
- [ ] Pull `postgres:15-alpine`
- [ ] Pull `python:3.11-slim`
- [ ] Build application image
- [ ] Save all images to tar.gz
- [ ] Verify tar.gz files created
- [ ] Transfer to disconnected environment

**Disconnected Environment:**
- [ ] Load images from tar.gz files
- [ ] Verify images loaded
- [ ] Tag images for private registry
- [ ] Login to private registry
- [ ] Push images to registry
- [ ] Verify images in registry
- [ ] Update values.yaml
- [ ] Create image pull secret (if needed)
- [ ] Deploy with Helm
- [ ] Verify deployment

---

## Quick Commands Reference

```bash
# Download (connected)
./scripts/download-images.sh

# Transfer (manual)
tar -czf images.tar.gz docker-images/
# Copy to disconnected environment

# Load (disconnected)
tar -xzf images.tar.gz
./scripts/load-images.sh

# Push (disconnected)
REGISTRY=your-registry.com ./scripts/push-to-registry.sh

# Deploy
helm upgrade --install server-scanner-dashboard \
  ./deploy/helm/server-scanner-dashboard \
  --namespace server-scanner \
  --set postgres.auth.password=PASSWORD

# Verify
kubectl get pods -n server-scanner
./scripts/verify-postgres-setup.sh server-scanner
```

---

## Additional Resources

- **Full Guide**: [DISCONNECTED_ENVIRONMENT_SETUP.md](DISCONNECTED_ENVIRONMENT_SETUP.md)
- **Migration Guide**: [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md)
- **Changes Summary**: [POSTGRES_CHANGES_SUMMARY.md](POSTGRES_CHANGES_SUMMARY.md)
