# Fix: bootstrap_mgr Exiting with Status 1 (rec-1, rec-2 Cannot Bootstrap)

**Symptom:** `bootstrap_mgr` process repeatedly spawns, enters RUNNING state, then exits with status 1 (not expected). Pods show "readiness probe failed: node id file does not exist - pod is not yet bootstrapped".

---

## Understanding the Problem

The `bootstrap_mgr` process is responsible for:
1. Connecting to rec-0 (the first node)
2. Getting a node ID from the cluster
3. Joining the cluster
4. Creating the node ID file (which makes the readiness probe pass)

**If `bootstrap_mgr` exits with status 1, it means it cannot complete one of these steps.**

---

## Step 1: Check bootstrap_mgr Logs (Detailed Error Messages)

The `bootstrap_mgr` logs will show **why** it's failing. Look for error messages **before** the "exited: bootstrap_mgr" line.

### In OpenShift UI:

1. Go to **Workloads** → **Pods**.
2. Open **rec-1** (or rec-2).
3. Go to **Logs** tab.
4. **Scroll up** from the "exited: bootstrap_mgr" messages to find the **actual error** that caused the exit.

### What to Look For:

- **"cannot connect to rec-0"** or **"connection refused"** → NetworkPolicy blocking or rec-0 not reachable
- **"timeout"** or **"connection timeout"** → Network connectivity issue
- **"cluster unreachable"** → Cannot reach rec-0's API
- **"storage"** or **"disk"** errors → PVC/storage issues
- **"permission denied"** → Security context or file permissions
- **"cluster not ready"** → rec-0 is not fully operational

---

## Step 2: Verify rec-0 is Ready and Reachable

rec-1 and rec-2 need to connect to **rec-0** to bootstrap. If rec-0 is not ready or unreachable, `bootstrap_mgr` will fail.

### Check rec-0 Status:

1. **Is rec-0 Ready?**
   - OpenShift: Workloads → Pods → rec-0 → Check **Ready = 1/1** (or 2/2)
   - kubectl: `kubectl get pod rec-0 -n <namespace>` → Check **READY** column

2. **Can rec-1 reach rec-0?**

   ```bash
   # Test from rec-1 to rec-0's REST API
   kubectl exec -it rec-1 -n <namespace> -- curl -k -v --connect-timeout 5 https://rec-0.rec:9443/v1/cluster
   
   # Or test using rec-0's pod IP
   kubectl get pod rec-0 -n <namespace> -o jsonpath='{.status.podIP}'
   kubectl exec -it rec-1 -n <namespace> -- curl -k -v --connect-timeout 5 https://<rec-0-pod-ip>:9443/v1/cluster
   ```

   **If this fails:** NetworkPolicy is blocking internode communication.

---

## Step 3: Check NetworkPolicy (Most Common Cause)

If `bootstrap_mgr` cannot connect to rec-0, NetworkPolicy is likely blocking internode communication.

### Verify NetworkPolicy is Applied:

```bash
kubectl get networkpolicy redis-enterprise-allow -n <namespace> -o yaml
```

**Check:**
- Does the policy exist?
- Does it have **egress** rules allowing REC pods to reach each other?
- Do egress rules include ports **3333-3345** and **20000-29999** (internode ports)?

### Apply/Update NetworkPolicy:

If NetworkPolicy is missing or incorrect:

```bash
# Apply the updated NetworkPolicy
kubectl apply -f redis-enterprise-network-policy.yaml -n <namespace>
```

**Then restart rec-1 and rec-2:**

```bash
kubectl delete pod rec-1 rec-2 -n <namespace>
```

---

## Step 4: Check Pod Logs for Specific Errors

Look for error messages **in the logs** (not just the "exited" messages). Common errors:

### Network Errors:

```
ERROR: cannot connect to rec-0:9443
ERROR: connection refused
ERROR: timeout connecting to cluster
```

**Fix:** NetworkPolicy blocking → Apply NetworkPolicy with internode egress rules.

### Storage Errors:

```
ERROR: cannot write node id file
ERROR: storage not available
ERROR: permission denied
```

**Fix:** Check PVC status, storage class, file permissions.

### Cluster Errors:

```
ERROR: cluster not ready
ERROR: rec-0 not responding
ERROR: invalid cluster state
```

**Fix:** Ensure rec-0 is Ready and cluster API is accessible.

---

## Step 5: Check REC Status and Cluster State

The REC status shows if the cluster is ready to accept new nodes.

```bash
kubectl get rec <rec-name> -n <namespace> -o yaml | grep -A 30 "status:"
```

**Check:**
- `status.state` → Should be "running" (not "creating" or "error")
- `status.readyNodes` → Should be at least 1 (rec-0)
- `status.conditions` → Look for False conditions with error messages

**If REC status shows errors:** Fix those first before rec-1/rec-2 can bootstrap.

---

## Step 6: Check Operator Logs

The operator manages the bootstrap process. Check if it's reporting issues.

```bash
# Find operator pod
kubectl get pods -A | grep redis-enterprise-operator

# Check logs for rec-1/rec-2 bootstrap
kubectl logs <operator-pod> -n <namespace> --tail=100 | grep -i "rec-1\|rec-2\|bootstrap\|join"
```

**Look for:**
- Errors about rec-1/rec-2 joining
- Messages about cluster state
- Network connectivity issues

---

## Common Root Causes and Fixes

| Root Cause | Symptoms in Logs | Fix |
|------------|-----------------|-----|
| **NetworkPolicy blocks internode** | "cannot connect to rec-0", "connection refused", "timeout" | Apply NetworkPolicy with egress rules for internode ports (3333-3345, 20000-29999) |
| **rec-0 not Ready** | "cluster unreachable", "rec-0 not responding" | Fix rec-0 (check logs, storage, resources) |
| **PVC not bound** | Storage errors, "cannot write node id file" | Fix PVC binding (storage class, quotas) |
| **Cluster not ready** | "cluster not ready", "invalid cluster state" | Check REC status, fix cluster state |
| **Wrong namespace/DNS** | "cannot resolve rec-0", DNS errors | Ensure all pods in same namespace |

---

## Quick Diagnostic Checklist

Run these checks **in order**:

- [ ] **Check rec-1 logs** → Scroll up from "exited" messages to find actual error
- [ ] **Test connectivity** → `kubectl exec -it rec-1 -n <namespace> -- curl -k https://rec-0.rec:9443/v1/cluster`
- [ ] **Check NetworkPolicy** → Verify egress rules for internode ports exist
- [ ] **Check rec-0** → Is it Ready? Can it be reached?
- [ ] **Check PVCs** → Are data-rec-1 and data-rec-2 Bound?
- [ ] **Check REC status** → Is cluster state "running"?
- [ ] **Check operator logs** → Any errors about bootstrap?

---

## Most Likely Fix

Based on `bootstrap_mgr` exiting with status 1:

**NetworkPolicy is blocking internode communication.**

**Steps:**

1. **Apply the updated NetworkPolicy:**
   ```bash
   kubectl apply -f redis-enterprise-network-policy.yaml -n <namespace>
   ```

2. **Verify it has egress rules:**
   ```bash
   kubectl get networkpolicy redis-enterprise-allow -n <namespace> -o yaml | grep -A 10 "egress:"
   ```

3. **Restart rec-1 and rec-2:**
   ```bash
   kubectl delete pod rec-1 rec-2 -n <namespace>
   ```

4. **Monitor logs** → `bootstrap_mgr` should now successfully connect to rec-0 and complete bootstrap.

---

## Next Steps

1. **Check rec-1 logs** → Find the actual error message (scroll up from "exited" messages)
2. **Share the error** → This will tell us exactly why `bootstrap_mgr` is failing
3. **Apply NetworkPolicy** → If not already applied
4. **Restart pods** → After fixing NetworkPolicy

The key is finding the **actual error message** in the logs that causes `bootstrap_mgr` to exit with status 1. That will tell us exactly what to fix.
