# Fix: All REC Pods Stuck in Bootstrap (rec-0, rec-1, rec-2)

**Symptom:** After restarting REC deployment from Argo CD, **all pods** (rec-0, rec-1, rec-2) show:
- Ready = **1/2** (not fully ready)
- "readiness probe failed: node id file does not exist - pod is not yet bootstrapped"
- `bootstrap_mgr` repeatedly exiting with status 1

---

## Understanding the Problem

**REC nodes bootstrap in order:**
1. **rec-0** must bootstrap first (creates the cluster)
2. **rec-1** joins rec-0 (after rec-0 is Ready)
3. **rec-2** joins the cluster (after rec-0 and rec-1 are Ready)

**If ALL pods are stuck, rec-0 is likely failing to bootstrap**, which prevents rec-1 and rec-2 from joining.

---

## Step 1: Check rec-0 Logs (Most Critical)

rec-0 is the **first node** and must bootstrap successfully before others can join.

### In OpenShift UI:

1. Go to **Workloads** → **Pods**.
2. Open **rec-0**.
3. Go to **Logs** tab.
4. **Scroll up** from "exited: bootstrap_mgr" messages to find the **actual error**.

### What to Look For:

- **Storage/PVC errors** → "cannot write", "permission denied", "storage not available"
- **Configuration errors** → "invalid config", "missing required settings"
- **Network errors** → "cannot bind", "port already in use"
- **Cluster initialization errors** → "failed to initialize cluster", "cluster creation failed"
- **Resource errors** → "out of memory", "CPU throttling"

### With kubectl:

```bash
# Check rec-0 logs
kubectl logs rec-0 -n <namespace> --tail=200

# Watch logs in real-time
kubectl logs -f rec-0 -n <namespace>
```

---

## Step 2: Check rec-0 Pod Events

Pod Events show **scheduling, storage, and startup issues**.

### In OpenShift UI:

1. Open **rec-0** → **Events** tab.
2. Look for:
   - **PVC** binding issues
   - **Image pull** errors
   - **Scheduling** failures
   - **Readiness probe** failures
   - **Container start** errors

### With kubectl:

```bash
kubectl describe pod rec-0 -n <namespace> | grep -A 30 "Events:"
```

---

## Step 3: Check PVC Status for All Pods

All REC pods need **PVCs** to be bound before they can bootstrap.

### In OpenShift UI:

1. Go to **Storage** → **PersistentVolumeClaims**.
2. Look for PVCs for rec-0, rec-1, rec-2 (e.g., **data-rec-0**, **data-rec-1**, **data-rec-2**).
3. Check **Status**:
   - ✅ **Bound** → PVC is ready
   - ❌ **Pending** → PVC is not bound → Check storage class, quotas, or node availability

### With kubectl:

```bash
kubectl get pvc -n <namespace> | grep rec
# Check STATUS column - all should be "Bound"
```

**If any PVC is Pending:**
- Check storage class: `kubectl get storageclass`
- Check resource quotas: `kubectl get resourcequota -n <namespace>`
- Check if nodes have available storage

---

## Step 4: Check REC Status and Cluster State

The REC status shows if the cluster is initializing or stuck.

### With kubectl:

```bash
kubectl get rec <rec-name> -n <namespace> -o yaml | grep -A 30 "status:"
```

**Check:**
- `status.state` → Should progress from "creating" → "running" (if stuck at "creating", check rec-0)
- `status.nodes` → Should be 3 (if all pods exist)
- `status.readyNodes` → Should increase as nodes bootstrap (0 = none ready yet)
- `status.conditions` → Look for False conditions with error messages

**If status shows errors:** Fix those first before pods can bootstrap.

---

## Step 5: Check Operator Logs

The operator manages the bootstrap process. Check if it's reporting issues.

### With kubectl:

```bash
# Find operator pod
kubectl get pods -A | grep redis-enterprise-operator

# Check logs for bootstrap/cluster initialization
kubectl logs <operator-pod> -n <namespace> --tail=200 | grep -i "rec-0\|bootstrap\|cluster\|init\|error"
```

**Look for:**
- Errors about rec-0 bootstrap
- Cluster initialization failures
- Configuration issues
- Resource constraints

---

## Step 6: Check if rec-0 Can Bind to Required Ports

rec-0 needs to bind to ports **9443** (REST API), **8443** (UI), **8001** (discovery), and internode ports.

### Check for port conflicts:

```bash
# Check if ports are already in use (from rec-0 logs or events)
kubectl logs rec-0 -n <namespace> | grep -i "port\|bind\|listen"
```

**If ports are in use:** Another process might be using them, or previous REC instance didn't clean up.

---

## Step 7: Check Resource Limits

If pods are hitting CPU/memory limits, bootstrap can fail.

### Check pod resource usage:

```bash
# Check if pods are OOMKilled or CPU throttled
kubectl describe pod rec-0 -n <namespace> | grep -i "oom\|throttle\|limit"
```

**If resources are insufficient:** Increase CPU/memory limits in REC spec.

---

## Common Root Causes and Fixes

| Root Cause | Symptoms | Fix |
|------------|----------|-----|
| **PVC not bound** | Storage errors in logs, PVC Status = Pending | Fix storage class, quotas, or node availability |
| **Storage permissions** | "permission denied", "cannot write node id file" | Check storage class, PVC mount permissions, SCC |
| **Cluster initialization failed** | rec-0 logs: "failed to initialize cluster" | Check rec-0 logs for specific error, fix configuration |
| **Port conflicts** | "port already in use", "cannot bind" | Clean up previous REC instances, check for port conflicts |
| **Resource limits** | OOMKilled, CPU throttling | Increase CPU/memory limits in REC spec |
| **Configuration errors** | "invalid config", "missing required settings" | Check REC spec, fix configuration |
| **NetworkPolicy blocking** | "cannot connect", but you tested connectivity works | Verify NetworkPolicy allows all required ports |

---

## Diagnostic Checklist

Run these checks **in order**:

- [ ] **Check rec-0 logs** → Find actual error causing bootstrap failure
- [ ] **Check rec-0 Events** → Look for PVC, scheduling, or container start errors
- [ ] **Check all PVCs** → Ensure data-rec-0, data-rec-1, data-rec-2 are Bound
- [ ] **Check REC status** → Look at state, readyNodes, conditions
- [ ] **Check operator logs** → Look for cluster initialization errors
- [ ] **Check resource usage** → Ensure pods aren't OOMKilled or throttled
- [ ] **Check port conflicts** → Ensure ports aren't already in use

---

## Most Likely Scenarios

### Scenario 1: rec-0 Cannot Initialize Cluster

**Symptoms:**
- rec-0 logs show "failed to initialize cluster" or similar
- REC status.state = "creating" (stuck)
- rec-0 bootstrap_mgr exits with status 1

**Fix:**
1. Check rec-0 logs for specific error
2. Fix the underlying issue (storage, config, resources)
3. Delete rec-0 pod to retry bootstrap

### Scenario 2: PVC Not Bound

**Symptoms:**
- PVC Status = Pending
- rec-0 logs show storage errors
- Pod Events show PVC binding issues

**Fix:**
1. Check storage class: `kubectl get storageclass`
2. Check resource quotas: `kubectl get resourcequota -n <namespace>`
3. Fix storage class or quotas
4. Delete pods to retry PVC binding

### Scenario 3: Storage Permissions

**Symptoms:**
- rec-0 logs: "permission denied", "cannot write node id file"
- PVC is Bound but pod cannot write

**Fix:**
1. Check Security Context Constraints (SCC) in OpenShift
2. Ensure REC pods have required permissions
3. Check PVC mount permissions

---

## What to Do Next

1. **Start with rec-0** → Check logs and Events (it must bootstrap first)
2. **Find the actual error** → Scroll up from "exited: bootstrap_mgr" to find the root cause
3. **Fix the underlying issue** → Storage, permissions, config, resources, etc.
4. **Restart rec-0** → After fixing, delete rec-0 pod to retry bootstrap
5. **Wait for rec-0 to be Ready** → Then rec-1 and rec-2 should join automatically

**The key is finding why rec-0 cannot bootstrap.** Once rec-0 is Ready, rec-1 and rec-2 should join successfully.

---

## Quick Commands

```bash
# 1. Check rec-0 logs
kubectl logs rec-0 -n <namespace> --tail=200

# 2. Check rec-0 events
kubectl describe pod rec-0 -n <namespace> | grep -A 20 "Events:"

# 3. Check all PVCs
kubectl get pvc -n <namespace> | grep rec

# 4. Check REC status
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.status}' | jq

# 5. Check operator logs
kubectl logs <operator-pod> -n <namespace> --tail=100 | grep -i "rec-0\|bootstrap\|error"
```

Share the **rec-0 logs** and **Events** — that will show exactly why bootstrap is failing.
