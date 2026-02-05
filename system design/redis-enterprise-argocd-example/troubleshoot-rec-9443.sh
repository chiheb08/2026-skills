#!/usr/bin/env bash
# Troubleshoot "get https://rec:9443/v1/nodes: context deadline exceeded" for rec-services-rigger.
# Run in a terminal; set NS or pass as first argument. Requires kubectl.
# Usage: ./troubleshoot-rec-9443.sh [namespace]   (default namespace: redis-enterprise)

NS="${1:-redis-enterprise}"
REC_NAME="${REC_NAME:-rec}"

echo "=== Namespace: $NS, REC name: $REC_NAME ==="
echo ""

echo "--- 1. Service '$REC_NAME' and endpoints ---"
if ! kubectl get svc "$REC_NAME" -n "$NS" 2>/dev/null; then
  echo "  -> Service '$REC_NAME' not found. Operator may not have created it yet. Fix REC bootstrap first (rec-bulletin-board, ignoreDifferences)."
else
  echo ""
  kubectl get endpoints "$REC_NAME" -n "$NS" -o yaml 2>/dev/null | grep -A 20 '^  subsets:' || echo "  -> No endpoints (no REC pod Ready). Get rec-0 Running and Ready first."
fi
echo ""

echo "--- 2. REC pods (cluster nodes) ---"
kubectl get pods -n "$NS" -l "app=$REC_NAME" --show-labels 2>/dev/null || true
kubectl get pods -n "$NS" | grep -E "^\s*${REC_NAME}-[0-9]" || echo "  -> No rec-* pods found."
echo "  -> If REC pods use a different label (e.g. redis.io/cluster: $REC_NAME), note it for NetworkPolicy podSelector."
echo ""

echo "--- 3. redis-enterprise-operator pod(s) ---"
kubectl get pods -n "$NS" | grep -E "redis-enterprise-operator|redis-enterprise-operator" || echo "  -> No operator pod found in $NS (may be in another namespace)."
OPPOD=$(kubectl get pods -n "$NS" -o name | grep redis-enterprise-operator | head -1)
if [ -n "$OPPOD" ]; then
  echo "  Labels for $OPPOD:"
  kubectl get "$OPPOD" -n "$NS" -o jsonpath='{.metadata.labels}' | tr ',' '\n' | sed 's/^/    /'
  echo "  -> Operator must be allowed to reach rec:9443 and <rec-pod-ip>:9443 (see NetworkPolicy redis-enterprise-operator rules)."
fi
echo ""

echo "--- 4. rec-services-rigger pod(s) ---"
kubectl get pods -n "$NS" | grep -E "services-rigger|services_rigger" || echo "  -> No services-rigger pod found."
RIGGER=$(kubectl get pods -n "$NS" -o name | grep -E "services-rigger|services_rigger" | head -1)
if [ -n "$RIGGER" ]; then
  echo "  Labels for $RIGGER:"
  kubectl get "$RIGGER" -n "$NS" -o jsonpath='{.metadata.labels}' | tr ',' '\n' | sed 's/^/    /'
fi
echo ""

echo "--- 5. NetworkPolicies in namespace ---"
kubectl get networkpolicy -n "$NS" 2>/dev/null || echo "  -> None."
echo ""

echo "--- 6. Quick connectivity test (from rec-services-rigger to rec:9443) ---"
if [ -z "$RIGGER" ]; then
  echo "  -> No services-rigger pod found; skip test."
else
  echo "  Run: kubectl exec -it $RIGGER -n $NS -- curl -k -v --connect-timeout 5 https://${REC_NAME}:9443/v1/nodes"
  echo "  Or:  kubectl exec -it $RIGGER -n $NS -- wget -O- --no-check-certificate --timeout=5 https://${REC_NAME}:9443/v1/nodes"
fi
echo ""

echo "--- 7. If error persists (operator + services-rigger) ---"
echo "  a) Ensure Service '$REC_NAME' has endpoints: kubectl get endpoints $REC_NAME -n $NS"
echo "  b) Ensure REC pods (e.g. ${REC_NAME}-0) are Running and Ready."
echo "  c) Apply both NetworkPolicies so REC pods are selected and operator/services-rigger allowed:"
echo "     - redis-enterprise-allow (includes redis-enterprise-operator, rec-services-rigger)"
echo "     - rec-allow-9443 (app: $REC_NAME)  <- for REC cluster pods labeled app: $REC_NAME"
echo "  d) If redis-enterprise-operator runs in a DIFFERENT namespace, uncomment and apply"
echo "     rec-allow-from-operator-namespace in redis-enterprise-network-policy.yaml."
echo "  e) If REC pods use different labels, edit podSelector.matchLabels to match rec-0's labels."
echo "  f) Temporarily delete NetworkPolicies to test: kubectl delete networkpolicy redis-enterprise-allow rec-allow-9443 -n $NS"
echo "     If the error stops, re-apply policies after fixing labels/namespace."
echo ""
