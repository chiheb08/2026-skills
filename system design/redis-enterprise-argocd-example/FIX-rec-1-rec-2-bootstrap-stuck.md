# Fix: rec-1 and rec-2 Stuck in Bootstrap ("node id file does not exist")

rec-1 and rec-2 show: **"readiness probe failed: node id file does not exist - pod is not yet bootstrapped"**

This is **normal during bootstrap**, but if they're stuck for more than 10-15 minutes, something is blocking them.

---

## Understanding the Bootstrap Process

When a new REC node (rec-1, rec-2) starts:

1. **Pod starts** → Container runs
2. **Readiness probe checks** → Looks for node ID file → **Fails** (expected, node not bootstrapped yet)
3. **REC node bootstraps** → Connects to rec-0, gets node ID, joins cluster
4. **Node ID file created** → Readiness probe passes → Pod becomes Ready

**Normal bootstrap time:** 5-15 minutes (depends on storage, network, resources).

**If stuck > 15 minutes:** Check the issues below.

---

## Step 1: Check Pod Logs (Most Important)

The pod logs will show **why** bootstrap is stuck.

### In OpenShift UI:

1. Go to **Workloads** → **Pods**.
2. Open **rec-1** (or rec-2).
3. Go to **Logs** tab.
4. Look for:
   - **Errors** about connecting to rec-0
   - **Errors** about storage/PVC
   - **Errors** about network connectivity
   - **Messages** about "waiting for cluster" or "joining cluster"

### With kubectl:

```bash
# Check rec-1 logs
kubectl logs rec-1 -n <namespace> --tail=100

# Check rec-2 logs
kubectl logs rec-2 -n <namespace> --tail=100

# Watch logs in real-time
kubectl logs -f rec-1 -n <namespace>
```

**What to look for:**
- **"cannot connect to rec-0"** or **"cluster unreachable"** → NetworkPolicy blocking internode communication
- **"storage"** or **"PVC"** errors → Storage issues
- **"timeout"** or **"connection refused"** → Network connectivity issues

---

## Step 2: Check Pod Events

Pod Events show **scheduling, storage, and startup issues**.

### In OpenShift UI:

1. Open **rec-1** → **Events** tab.
2. Look for:
   - **PVC** binding issues
   - **Image pull** errors
   - **Scheduling** failures
   - **Readiness probe** failures (expected, but check frequency)

### With kubectl:

```bash
kubectl describe pod rec-1 -n <namespace> | grep -A 20 "Events:"
```

---

## Step 3: Check PVC Status

rec-1 and rec-2 need **PVCs** to be bound before they can bootstrap.

### In OpenShift UI:

1. Go to **Storage** → **PersistentVolumeClaims**.
2. Look for PVCs named like **data-rec-1** and **data-rec-2** (or similar pattern).
3. Check **Status**:
   - ✅ **Bound** → PVC is ready
   - ❌ **Pending** → PVC is not bound → Check storage class, quotas, or node availability

### With kubectl:

```bash
kubectl get pvc -n <namespace> | grep rec
# Check STATUS column - should be "Bound"
```

**If PVC is Pending:**
- Check storage class: `kubectl get storageclass`
- Check if nodes have available storage
- Check resource quotas: `kubectl get resourcequota -n <namespace>`

---

## Step 4: Check NetworkPolicy for Internode Communication

rec-1 and rec-2 need to **communicate with rec-0** (and each other) on **internode ports** (typically 3333-3345, 20000-29999, etc.).

### Check if NetworkPolicy blocks internode traffic:

1. Go to **Networking** → **Network Policies**.
2. Check policies that apply to REC pods (e.g. **redis-enterprise-allow**).
3. Ensure **egress** rules allow REC pods to reach **other REC pods** on internode ports.

**Common issue:** NetworkPolicy allows ingress from rec-services-rigger but **doesn't allow internode communication** between rec-0, rec-1, rec-2.

**Fix:** Add egress rules (or use `podSelector: {}` for egress) so REC pods can reach each other.

### Example NetworkPolicy fix:

```yaml
# In redis-enterprise-allow policy, ensure egress allows internode:
egress:
  # Allow REC pods to reach each other (internode communication)
  - to:
      - podSelector:
          matchLabels:
            app: redis-enterprise
            redis.io/cluster: rec
    ports:
      - protocol: TCP
        port: 3333-3345    # Internode ports
      - protocol: TCP
        port: 20000-29999  # Internode ports
```

---

## Step 5: Check if rec-0 is Ready and Reachable

rec-1 and rec-2 need to **connect to rec-0** to join the cluster.

### Verify rec-0:

1. **Is rec-0 Ready?**
   - OpenShift: Workloads → Pods → rec-0 → Check **Ready = 1/1**
   - kubectl: `kubectl get pod rec-0 -n <namespace>` → Check **READY** column

2. **Can rec-1/rec-2 reach rec-0?**
   - Test from rec-1: `kubectl exec -it rec-1 -n <namespace> -- curl -k https://rec-0.rec:9443/v1/cluster`
   - Or check if rec-0's IP is reachable from rec-1

3. **Is rec-0's API (9443) accessible?**
   - From rec-services-rigger: Should work (you fixed this earlier)
   - From rec-1/rec-2: Should also work if NetworkPolicy allows internode

---

## Step 6: Check Operator Logs

The operator manages the bootstrap process. Check if it's reporting issues.

### With kubectl:

```bash
# Find operator pod
kubectl get pods -A | grep redis-enterprise-operator

# Check logs for rec-1/rec-2 bootstrap
kubectl logs <operator-pod> -n <namespace> --tail=100 | grep -i "rec-1\|rec-2\|bootstrap\|join"
```

**Look for:**
- Errors about rec-1/rec-2 joining
- Messages about waiting for nodes
- Cluster state issues

---

## Step 7: Check REC Status

The REC status shows cluster state and conditions.

### With kubectl:

```bash
kubectl get rec <rec-name> -n <namespace> -o yaml | grep -A 30 "status:"
```

**Check:**
- `status.nodes` (should be 3 if all pods exist)
- `status.readyNodes` (should increase as nodes bootstrap)
- `status.state` (should be "running" or "scaling")
- `status.conditions` (look for False conditions with messages)

---

## Common Root Causes and Fixes

| Issue | Symptoms | Fix |
|-------|----------|-----|
| **NetworkPolicy blocks internode** | rec-1 logs: "cannot connect to rec-0" or "timeout" | Add egress rules to NetworkPolicy allowing REC pods to reach each other on internode ports (3333-3345, 20000-29999) |
| **PVC not bound** | PVC Status = Pending | Fix storage class, quotas, or node availability |
| **rec-0 not reachable** | rec-1 logs: "cluster unreachable" | Ensure rec-0 is Ready and NetworkPolicy allows rec-1 → rec-0 |
| **Storage issues** | Pod logs: storage errors | Check PVC, storage class, node storage |
| **Resource limits** | Pod Events: OOMKilled or CPU throttling | Increase CPU/memory limits in REC spec |
| **Slow bootstrap (normal)** | Readiness probe fails but logs show progress | Wait 10-15 minutes; bootstrap can take time |

---

## Quick Diagnostic Commands

```bash
# 1. Check pod status
kubectl get pods -n <namespace> | grep "^rec-"

# 2. Check PVC status
kubectl get pvc -n <namespace> | grep rec

# 3. Check rec-1 logs
kubectl logs rec-1 -n <namespace> --tail=50

# 4. Check rec-1 events
kubectl describe pod rec-1 -n <namespace> | grep -A 10 "Events:"

# 5. Test connectivity from rec-1 to rec-0
kubectl exec -it rec-1 -n <namespace> -- curl -k -v --connect-timeout 5 https://rec-0.rec:9443/v1/cluster

# 6. Check NetworkPolicies
kubectl get networkpolicy -n <namespace>

# 7. Check REC status
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.status}' | jq
```

---

## Most Likely Fix

Based on your situation (manually scaled to 3, rec-1/rec-2 stuck in bootstrap):

**NetworkPolicy is blocking internode communication.**

**Fix:**
1. Go to **Networking** → **Network Policies**.
2. Open **redis-enterprise-allow** (or the policy that applies to REC pods).
3. Ensure **egress** rules allow REC pods (`app: redis-enterprise`, `redis.io/cluster: rec`) to reach **each other** on internode ports (3333-3345, 20000-29999).
4. If the policy uses `podSelector: {}` for egress, that should work, but verify it's applied to REC pods.
5. **Restart rec-1 and rec-2** after fixing NetworkPolicy:
   - `kubectl delete pod rec-1 rec-2 -n <namespace>`
   - They will be recreated and should bootstrap successfully.

---

## Summary

1. **Check pod logs** → Shows why bootstrap is stuck
2. **Check PVC status** → Must be Bound
3. **Check NetworkPolicy** → Must allow internode communication
4. **Check rec-0** → Must be Ready and reachable
5. **Wait 10-15 minutes** → Bootstrap can take time (normal)
6. **If still stuck** → Check operator logs and REC status

The "node id file does not exist" message is **normal during bootstrap**. If pods are stuck for > 15 minutes, check logs and NetworkPolicy for internode communication.
