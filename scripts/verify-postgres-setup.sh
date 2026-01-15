#!/bin/bash
#
# PostgreSQL Setup Verification Script
#
# This script verifies the PostgreSQL deployment in Kubernetes and tests
# the database connection and schema.
#
# Usage:
#   ./verify-postgres-setup.sh [namespace]
#
# Example:
#   ./verify-postgres-setup.sh server-scanner
#

set -e

NAMESPACE="${1:-server-scanner}"
RELEASE_NAME="server-scanner-dashboard"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "PostgreSQL Setup Verification"
echo "Namespace: $NAMESPACE"
echo "=========================================="
echo

# Function to print status
print_status() {
    local status=$1
    local message=$2

    if [ "$status" == "success" ]; then
        echo -e "${GREEN}✓${NC} $message"
    elif [ "$status" == "warning" ]; then
        echo -e "${YELLOW}⚠${NC} $message"
    else
        echo -e "${RED}✗${NC} $message"
    fi
}

# 1. Check if namespace exists
echo "1. Checking namespace..."
if kubectl get namespace "$NAMESPACE" &> /dev/null; then
    print_status "success" "Namespace '$NAMESPACE' exists"
else
    print_status "error" "Namespace '$NAMESPACE' does not exist"
    echo "   Create it with: kubectl create namespace $NAMESPACE"
    exit 1
fi
echo

# 2. Check PostgreSQL pod
echo "2. Checking PostgreSQL pod..."
PGPOD=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=database -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -z "$PGPOD" ]; then
    print_status "error" "PostgreSQL pod not found"
    echo "   Deploy with: helm upgrade --install $RELEASE_NAME ./deploy/helm/server-scanner-dashboard -n $NAMESPACE"
    exit 1
fi

POD_STATUS=$(kubectl get pod "$PGPOD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
if [ "$POD_STATUS" == "Running" ]; then
    print_status "success" "PostgreSQL pod '$PGPOD' is Running"
else
    print_status "error" "PostgreSQL pod '$PGPOD' is $POD_STATUS"
    echo "   Check with: kubectl describe pod $PGPOD -n $NAMESPACE"
    exit 1
fi
echo

# 3. Check PostgreSQL service
echo "3. Checking PostgreSQL service..."
if kubectl get svc "${RELEASE_NAME}-postgres" -n "$NAMESPACE" &> /dev/null; then
    print_status "success" "PostgreSQL service exists"
    SERVICE_IP=$(kubectl get svc "${RELEASE_NAME}-postgres" -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    echo "   Cluster IP: $SERVICE_IP:5432"
else
    print_status "warning" "PostgreSQL service not found"
fi
echo

# 4. Check PVC
echo "4. Checking PersistentVolumeClaim..."
PVC_NAME=$(kubectl get pvc -n "$NAMESPACE" -l app.kubernetes.io/component=database -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$PVC_NAME" ]; then
    PVC_STATUS=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    if [ "$PVC_STATUS" == "Bound" ]; then
        print_status "success" "PVC '$PVC_NAME' is Bound"
        PVC_SIZE=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" -o jsonpath='{.status.capacity.storage}')
        echo "   Size: $PVC_SIZE"
    else
        print_status "warning" "PVC '$PVC_NAME' is $PVC_STATUS"
    fi
else
    print_status "warning" "No PVC found (persistence might be disabled)"
fi
echo

# 5. Check PostgreSQL secret
echo "5. Checking PostgreSQL secret..."
if kubectl get secret "${RELEASE_NAME}-postgres" -n "$NAMESPACE" &> /dev/null; then
    print_status "success" "PostgreSQL secret exists"

    # Verify secret has required keys
    if kubectl get secret "${RELEASE_NAME}-postgres" -n "$NAMESPACE" -o jsonpath='{.data.username}' &> /dev/null; then
        print_status "success" "Secret contains 'username' key"
    else
        print_status "error" "Secret missing 'username' key"
    fi

    if kubectl get secret "${RELEASE_NAME}-postgres" -n "$NAMESPACE" -o jsonpath='{.data.password}' &> /dev/null; then
        print_status "success" "Secret contains 'password' key"
    else
        print_status "error" "Secret missing 'password' key"
    fi
else
    print_status "error" "PostgreSQL secret not found"
fi
echo

# 6. Test database connection
echo "6. Testing database connection..."
if kubectl exec -it "$PGPOD" -n "$NAMESPACE" -- pg_isready -U scanner &> /dev/null; then
    print_status "success" "PostgreSQL is accepting connections"
else
    print_status "error" "PostgreSQL is not accepting connections"
    echo "   Check logs with: kubectl logs $PGPOD -n $NAMESPACE"
    exit 1
fi
echo

# 7. Check database exists
echo "7. Checking database 'server_scanner'..."
DB_EXISTS=$(kubectl exec -it "$PGPOD" -n "$NAMESPACE" -- psql -U scanner -lqt | cut -d \| -f 1 | grep -w server_scanner | wc -l)

if [ "$DB_EXISTS" -gt 0 ]; then
    print_status "success" "Database 'server_scanner' exists"
else
    print_status "warning" "Database 'server_scanner' not found"
    echo "   It will be created on first application startup"
fi
echo

# 8. Check table exists
echo "8. Checking table 'server_maintenance'..."
TABLE_EXISTS=$(kubectl exec -it "$PGPOD" -n "$NAMESPACE" -- \
    psql -U scanner -d server_scanner -tAc \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'server_maintenance');" 2>/dev/null || echo "f")

if [ "$TABLE_EXISTS" == "t" ]; then
    print_status "success" "Table 'server_maintenance' exists"

    # Get record count
    RECORD_COUNT=$(kubectl exec -it "$PGPOD" -n "$NAMESPACE" -- \
        psql -U scanner -d server_scanner -tAc \
        "SELECT COUNT(*) FROM server_maintenance;" 2>/dev/null || echo "0")

    echo "   Records: $RECORD_COUNT"

    # Check indexes
    echo ""
    echo "   Indexes:"
    kubectl exec -it "$PGPOD" -n "$NAMESPACE" -- \
        psql -U scanner -d server_scanner -c \
        "SELECT indexname FROM pg_indexes WHERE tablename = 'server_maintenance';" 2>/dev/null | grep -v "^$" | grep -v "indexname" | grep -v "^-" | while read idx; do
        echo "     - $idx"
    done

else
    print_status "warning" "Table 'server_maintenance' not found"
    echo "   It will be created on first application startup"
fi
echo

# 9. Check application pod
echo "9. Checking application pod..."
APP_POD=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=server-scanner-dashboard -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$APP_POD" ]; then
    APP_STATUS=$(kubectl get pod "$APP_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')

    if [ "$APP_STATUS" == "Running" ]; then
        print_status "success" "Application pod '$APP_POD' is Running"

        # Check for PostgreSQL in logs
        if kubectl logs "$APP_POD" -n "$NAMESPACE" --tail=100 2>/dev/null | grep -q "PostgreSQL"; then
            print_status "success" "Application is using PostgreSQL backend"
        else
            print_status "warning" "Cannot confirm PostgreSQL backend from logs"
        fi
    else
        print_status "warning" "Application pod '$APP_POD' is $APP_STATUS"
    fi
else
    print_status "warning" "Application pod not found"
fi
echo

# 10. Test a simple query
echo "10. Testing database operations..."
if [ "$TABLE_EXISTS" == "t" ]; then
    # Try a simple SELECT query
    if kubectl exec -it "$PGPOD" -n "$NAMESPACE" -- \
        psql -U scanner -d server_scanner -c "SELECT 1;" &> /dev/null; then
        print_status "success" "Database queries working"
    else
        print_status "error" "Database query failed"
    fi
else
    print_status "warning" "Skipping query test (table doesn't exist yet)"
fi
echo

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo
echo "PostgreSQL Pod:     $PGPOD"
echo "PostgreSQL Service: ${RELEASE_NAME}-postgres"
echo "Database:           server_scanner"
echo "Table:              server_maintenance"

if [ -n "$APP_POD" ]; then
    echo "Application Pod:    $APP_POD"
fi

echo
echo "Next Steps:"
echo "  1. Verify application logs: kubectl logs $APP_POD -n $NAMESPACE"
echo "  2. Test API endpoint: curl https://\$ROUTE/api/servers"
echo "  3. Migrate existing data: python scripts/migrate-json-to-postgres.py"
echo "  4. Check migration guide: docs/POSTGRES_MIGRATION.md"
echo

echo "=========================================="
echo "✓ Verification Complete"
echo "=========================================="
