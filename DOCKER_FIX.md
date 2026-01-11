# Docker Fix - uvicorn Not Found in PATH

## Problem

When running the Docker container, it failed with:
```
Error container create failed runc create failed to start container process
exec uvicorn executable file not found in $PATH
```

## Root Cause

The issue had two problems:

1. **PATH Order**: The `ENV PATH=/home/scanner/.local/bin:$PATH` was set AFTER switching to the non-root user, but environment variables set after USER don't affect the CMD execution context reliably.

2. **Executable vs Module**: The CMD was trying to run `uvicorn` as an executable, which relies on the PATH being correctly set. This is less reliable than using Python module execution.

## Fix

### Change 1: Move PATH Before User Switch

```dockerfile
# Before
# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/scanner/.local
# Copy application code
COPY --chown=scanner:scanner . .
# Switch to non-root user
USER scanner
# Add local bin to PATH
ENV PATH=/home/scanner/.local/bin:$PATH

# After
# Add local bin to PATH (before switching user)
ENV PATH=/home/scanner/.local/bin:$PATH
# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/scanner/.local
# Copy application code
COPY --chown=scanner:scanner . .
# Switch to non-root user
USER scanner
```

### Change 2: Run Python Script Directly

```dockerfile
# Before
CMD ["uvicorn", "src.web_ui:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# After
CMD ["python", "src/web_ui.py", "--host", "0.0.0.0", "--port", "8000"]
```

## Why This Works

1. **`python` is always in PATH**: The base Python image ensures `python` is in the system PATH
2. **Direct script execution**: Runs `src/web_ui.py` which imports and calls `uvicorn.run()` programmatically
3. **No PATH dependency**: Don't need to rely on `/home/scanner/.local/bin` being in PATH or uvicorn executable
4. **Simpler**: Uses the same method as running locally (`python src/web_ui.py`)

## Testing

```bash
# Build the image
podman build -t server-scanner-dashboard .

# Run the container
podman run -p 8000:8000 --env-file .env server-scanner-dashboard

# Test the endpoint
curl http://localhost:8000/api/cache/status
```

## Alternative Solutions

If you prefer to use the executable directly, you can also use the full path:

```dockerfile
CMD ["/home/scanner/.local/bin/uvicorn", "src.web_ui:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

However, `python -m uvicorn` is the recommended approach because:
- More portable across different base images
- Doesn't depend on specific installation paths
- Standard Python practice

## Environment Variables vs .env File

### Issue 3: Container Looking for .env File

**Problem**: The application was calling `load_dotenv()` unconditionally, causing it to look for a `.env` file even in Docker/Kubernetes deployments where environment variables are already set.

**Fix**: Modified [src/config.py](src/config.py#L19-23) to only load `.env` if the file exists:

```python
# Only load .env if file exists (for local development)
if Path(".env").exists():
    load_dotenv()
else:
    # In production (Docker/K8s), env vars are set directly - no .env needed
    pass
```

**Why This Works**:
1. **Local Development**: If `.env` exists, load it automatically
2. **Docker/Kubernetes**: Environment variables are passed directly via `-e` or configmaps/secrets
3. **Flexible**: Works in both environments without modification

## Files Modified

- **Dockerfile**: Lines 40-41 (PATH moved before USER), Line 64 (CMD changed to use `python`)
- **src/config.py**: Lines 19-23 (conditional .env loading)
- **requirements.txt**: Lines 11-12 (fixed Cisco UCS SDK versions)

## Verification

### Build and Run with Environment Variables

```bash
# Build the image
podman build -t server-scanner-dashboard .

# Run with environment variables (no .env file needed)
podman run -d -p 8000:8000 \
  -e ONEVIEW_IP=10.0.0.1 \
  -e ONEVIEW_USERNAME=admin \
  -e ONEVIEW_PASSWORD=secret \
  -e K8S_CLUSTER_NAMES=cluster1,cluster2 \
  -e K8S_DOMAIN_NAME=example.com \
  -e K8S_TOKEN=token1,token2 \
  server-scanner-dashboard

# Check container logs
podman logs <container-id>

# Should see:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Configuration validated: 1 vendor(s) configured
# INFO:     Application startup complete.
```

### Or Run with .env File (for local testing)

```bash
# If you prefer to use .env file
podman run -d -p 8000:8000 --env-file .env server-scanner-dashboard
```
