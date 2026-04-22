#!/usr/bin/env bash
# bootstrap-k8s-sa.sh
# Creates the server-scanner namespace, service account, cluster-admin binding,
# and a long-lived token secret, then prints the token for use in values.yaml.
#
# Usage: ./deploy/bootstrap-k8s-sa.sh [namespace]
# Default namespace: server-scanner

set -euo pipefail

NAMESPACE="${1:-server-scanner}"
SA_NAME="server-scanner"
SECRET_NAME="server-scanner-token"

echo "==> Creating namespace: ${NAMESPACE}"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Creating ServiceAccount: ${SA_NAME}"
kubectl create serviceaccount "${SA_NAME}" \
  --namespace "${NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Binding cluster-admin to ServiceAccount"
kubectl create clusterrolebinding "${SA_NAME}-cluster-admin" \
  --clusterrole=cluster-admin \
  --serviceaccount="${NAMESPACE}:${SA_NAME}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Creating long-lived token Secret"
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${SECRET_NAME}
  namespace: ${NAMESPACE}
  annotations:
    kubernetes.io/service-account.name: "${SA_NAME}"
type: kubernetes.io/service-account-token
EOF

echo "==> Waiting for token to be populated..."
for i in $(seq 1 10); do
  TOKEN=$(kubectl get secret "${SECRET_NAME}" \
    --namespace "${NAMESPACE}" \
    -o jsonpath='{.data.token}' 2>/dev/null | base64 -d 2>/dev/null || true)
  if [ -n "${TOKEN}" ]; then
    break
  fi
  sleep 2
done

if [ -z "${TOKEN}" ]; then
  echo "ERROR: Token was not populated after 20s. Check the secret manually:"
  echo "  kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o yaml"
  exit 1
fi

echo ""
echo "================================================================"
echo "  Token ready. Add to your Helm values (values.yaml / secret):"
echo "================================================================"
echo ""
echo "secrets:"
echo "  k8sToken: \"${TOKEN}\""
echo ""
echo "Or as a one-liner for helm install --set:"
echo "  --set secrets.k8sToken=\"${TOKEN}\""
echo ""
echo "Namespace for values.yaml:"
echo "  config:"
echo "    k8sNamespace: \"${NAMESPACE}\""
