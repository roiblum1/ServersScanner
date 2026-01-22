#!/bin/bash
# Verification script for src/ reorganization

echo "==================================================================="
echo "Server Scanner Dashboard - Structure Verification"
echo "==================================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
PASS=0
FAIL=0

# Helper functions
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} File exists: $1"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} File missing: $1"
        ((FAIL++))
    fi
}

check_import() {
    local file=$1
    local pattern=$2
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Import correct in $file"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} Import missing in $file: $pattern"
        ((FAIL++))
    fi
}

check_syntax() {
    local file=$1
    if python -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Syntax valid: $file"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} Syntax error: $file"
        ((FAIL++))
    fi
}

# 1. Check file locations
echo "1. Checking file locations..."
echo "-------------------------------------------------------------------"
check_file "src/config.py"
check_file "src/scan_servers.py"
check_file "src/web_ui.py"
check_file "src/__init__.py"
check_file "Dockerfile"
check_file "docker-compose.yml"
echo ""

# 2. Check Python syntax
echo "2. Checking Python syntax..."
echo "-------------------------------------------------------------------"
check_syntax "src/config.py"
check_syntax "src/scan_servers.py"
check_syntax "src/web_ui.py"
echo ""

# 3. Check imports
echo "3. Checking import statements..."
echo "-------------------------------------------------------------------"
check_import "src/web_ui.py" "from src.config import"
check_import "src/scan_servers.py" "from src.services import"
echo ""

# 4. Check Dockerfile
echo "4. Checking Dockerfile..."
echo "-------------------------------------------------------------------"
if grep -q '"src.web_ui:app"' Dockerfile; then
    echo -e "${GREEN}✓${NC} Dockerfile CMD uses correct module path"
    ((PASS++))
else
    echo -e "${RED}✗${NC} Dockerfile CMD has incorrect module path"
    ((FAIL++))
fi
echo ""

# 5. Check CLI help
echo "5. Checking CLI tools..."
echo "-------------------------------------------------------------------"
if python -m src.scan_servers --help > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} scan_servers CLI works"
    ((PASS++))
else
    echo -e "${RED}✗${NC} scan_servers CLI failed"
    ((FAIL++))
fi

# Note: web_ui might fail if FastAPI not installed, which is OK
if python -m src.web_ui --help > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} web_ui CLI works"
    ((PASS++))
else
    echo -e "${YELLOW}⚠${NC} web_ui CLI failed (may need FastAPI installed)"
fi
echo ""

# 6. Check documentation
echo "6. Checking documentation..."
echo "-------------------------------------------------------------------"
check_file "README.md"
check_file "MULTI_POD_ANALYSIS.md"
check_file "MIGRATION_TO_SRC.md"
check_file "CHANGES_SUMMARY.md"
echo ""

# 7. Check project structure
echo "7. Checking directory structure..."
echo "-------------------------------------------------------------------"
for dir in src/filters src/formatters src/models src/parsers src/repositories src/services src/strategies static/html static/css static/js deploy/helm; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} Directory exists: $dir"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} Directory missing: $dir"
        ((FAIL++))
    fi
done
echo ""

# Summary
echo "==================================================================="
echo "VERIFICATION SUMMARY"
echo "==================================================================="
echo -e "${GREEN}Passed:${NC} $PASS"
if [ $FAIL -gt 0 ]; then
    echo -e "${RED}Failed:${NC} $FAIL"
else
    echo -e "${GREEN}Failed:${NC} $FAIL"
fi
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Structure is correct.${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Build Docker image: docker build -t scanner ."
    echo "  - Run locally: python -m src.web_ui --verbose"
    echo "  - Deploy to OpenShift: helm install scanner deploy/helm/server-scanner-dashboard"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please review the errors above.${NC}"
    exit 1
fi
