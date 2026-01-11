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

### Change 2: Use Python Module Execution

```dockerfile
# Before
CMD ["uvicorn", "src.web_ui:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# After
CMD ["python", "-m", "uvicorn", "src.web_ui:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

## Why This Works

1. **`python` is always in PATH**: The base Python image ensures `python` is in the system PATH
2. **`-m` flag**: Tells Python to run a module as a script, so it finds `uvicorn` in the installed packages
3. **No PATH dependency**: Don't need to rely on `/home/scanner/.local/bin` being in PATH

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

## Files Modified

- **Dockerfile**: Lines 40-41 (PATH moved before USER), Line 64 (CMD changed to use `python -m`)

## Verification

After rebuilding, verify the container starts correctly:

```bash
# Check container logs
podman logs <container-id>

# Should see:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
```
