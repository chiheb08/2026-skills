# Deep Dive: Why Only rec-0 Exists (No rec-1, rec-2)

You have `spec.nodes: 3` but only **rec-0** exists (Running and Ready). rec-1 and rec-2 (and their PVCs) are not created.

**This guide walks through systematic checks to find the root cause.**

---

## Step 1: Check StatefulSet Replicas

**The StatefulSet is what actually creates rec-0, rec-1, rec-2.** If replicas = 1, only rec-0 will exist.

### In OpenShift UI:

1. Go to **Workloads** → **StatefulSets**.
2. Find the StatefulSet that owns rec-0 (name usually matches your REC name, e.g. **rec**).
3. Check **Desired** / **Replicas**:
   - **If replicas = 1** → The operator has only requested 1 replica. Go to **Step 2** (check REC status and operator logs).
   - **If replicas = 3** but only rec-0 exists → rec-1/rec-2 are likely **Pending**. Go to **Step 5** (check pod Events).

### With kubectl:

```bash
kubectl get statefulset -n <namespace> | grep rec
# Look at the DESIRED and CURRENT columns

# Or get details:
kubectl get statefulset <rec-name> -n <namespace> -o yaml
# Check spec.replicas vs status.replicas
```

---

## Step 2: Check REC Status (nodes, readyNodes, state, conditions)

The **RedisEnterpriseCluster status** shows what the operator thinks about the cluster state. This is critical.

### In OpenShift UI:

1. Go to **Workloads** → **Redis Enterprise Clusters** (or search for your REC by name).
2. Open your REC → **YAML** tab.
3. Scroll to the **status** section and check:

   ```yaml
   status:
     nodes: 1          # ← How many nodes the operator thinks exist
     readyNodes: 1     # ← How many are ready
     state: "..."      # ← Cluster state (e.g. "running", "creating", "scaling")
     conditions:       # ← Array of conditions explaining status
       - type: "..."
         status: "..."
         message: "..."
   ```

**What to look for:**

- **status.nodes = 1** but **spec.nodes = 3** → Operator hasn't scaled yet. Check **status.state** and **status.conditions** for why.
- **status.state = "creating"** or **"scaling"** → Operator is still working. Check conditions for blockers.
- **status.conditions** → Look for conditions with `status: "False"` or `type: "Ready"` with `status: "False"` and read the **message** field.

### With kubectl:

```bash
# Get REC status
kubectl get rec <rec-name> -n <namespace> -o yaml | grep -A 20 "status:"

# Or just status:
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.status}' | jq
```

---

## Step 3: Check Operator Logs

The operator logs will show **why** it's not creating rec-1/rec-2.

### In OpenShift UI:

1. Go to **Workloads** → **Pods**.
2. Find the **redis-enterprise-operator** pod (might be in a different namespace, e.g. `operators` or `redis-enterprise`).
3. Open it → **Logs** tab.
4. Look for:
   - Messages about **scaling** or **creating nodes**
   - Errors about **rec:9443** or **RS API**
   - Messages about **waiting for cluster to be ready**
   - Warnings about **conditions** or **status**

### With kubectl:

```bash
# Find operator pod
kubectl get pods -A | grep redis-enterprise-operator

# Get logs (replace <namespace> and <pod-name>)
kubectl logs <pod-name> -n <namespace> --tail=100 | grep -i "rec\|node\|scale\|9443"

# Or watch logs:
kubectl logs -f <pod-name> -n <namespace>
```

**What to look for:**
- **"waiting for cluster API"** or **"RS API is not available"** → Operator is waiting for rec:9443 to be reachable before scaling. Fix NetworkPolicy (see SOLUTION-rec-9443-timeout.md).
- **"cluster not ready"** → Check REC status.conditions for details.
- **No scaling messages** → Operator might not be reconciling. Check if operator is healthy.

---

## Step 4: Check if rec:9443 is Reachable (Most Common Blocker)

The operator often **waits for rec:9443 to be reachable** before creating rec-1/rec-2. This is a safety feature.

### Check rec-services-rigger logs:

```bash
# Find rec-services-rigger pod
kubectl get pods -n <namespace> | grep services-rigger

# Check logs
kubectl logs <pod-name> -n <namespace> --tail=50
```

**If you see:**
- `get "https://rec:9443/v1/nodes": context deadline exceeded` → **NetworkPolicy is blocking**. Fix this first (see SOLUTION-rec-9443-timeout.md).

### Test connectivity from rec-services-rigger:

```bash
# Exec into rec-services-rigger pod
kubectl exec -it <rec-services-rigger-pod> -n <namespace> -- sh

# Test connectivity
curl -k -v --connect-timeout 5 https://rec:9443/v1/nodes
```

If this fails, fix NetworkPolicy and restart rec-services-rigger.

---

## Step 5: Check if rec-1/rec-2 Exist but are Pending

If **StatefulSet replicas = 3** but you only see rec-0, rec-1/rec-2 might exist but be **Pending**.

### In OpenShift UI:

1. Go to **Workloads** → **Pods**.
2. Filter by name or labels (e.g. `app=redis-enterprise`, `redis.io/cluster=rec`).
3. Look for **rec-1** and **rec-2**:
   - If they exist but **Status = Pending** → Open each pod and check **Events** and **Conditions** tabs.

**Common reasons for Pending:**
- **PVC not bound** → Check Storage → PersistentVolumeClaims. If rec-1/rec-2 PVCs are **Pending**, check storage class, quotas, or node availability.
- **CPU/memory quota exhausted** → Check Resource Quotas in the namespace.
- **Node selector / taints** → No nodes can schedule rec-1/rec-2.

### With kubectl:

```bash
# Check all rec-* pods
kubectl get pods -n <namespace> | grep "^rec-"

# If rec-1/rec-2 exist but are Pending:
kubectl describe pod rec-1 -n <namespace>
# Look at Events and Conditions sections
```

---

## Step 6: Check Argo CD Sync Status

If Argo CD is managing the REC, check if it's overwriting the StatefulSet.

### In Argo CD UI:

1. Open your Redis application.
2. Check the **StatefulSet** resource (if it appears):
   - Is it **Synced** or **OutOfSync**?
   - What does the **live manifest** show for `spec.replicas`?
   - If Argo CD shows `replicas: 1` in Git but the operator set `replicas: 3`, Argo CD might be reverting it.

**Fix:**
- The StatefulSet should **not** be in your Git repo (operator creates it).
- If it is, remove it or add `ignoreDifferences` for the StatefulSet so Argo CD doesn't change `spec.replicas`.
- Ensure `ignoreDifferences` for REC `.status` is set (see `application.yaml`).

---

## Step 7: Check REC Spec vs Status

Compare what you **want** (`spec.nodes: 3`) vs what the operator **has** (`status.nodes: 1`).

### With kubectl:

```bash
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.spec.nodes}' && echo " (desired)"
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.status.nodes}' && echo " (current)"
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.status.readyNodes}' && echo " (ready)"
kubectl get rec <rec-name> -n <namespace> -o jsonpath='{.status.state}' && echo " (state)"
```

**If spec.nodes = 3 but status.nodes = 1:**
- Operator hasn't scaled yet. Check status.conditions and operator logs for why.

---

## Common Root Causes and Fixes

| Root Cause | How to Identify | Fix |
|------------|-----------------|-----|
| **NetworkPolicy blocks rec:9443** | rec-services-rigger logs: timeout to rec:9443 | Create NetworkPolicies allowing traffic to REC pods on 9443 (see SOLUTION-rec-9443-timeout.md) |
| **Operator waiting for rec:9443** | Operator logs: "waiting for cluster API" or "RS API not available" | Fix rec:9443 connectivity, restart rec-services-rigger |
| **REC status.conditions shows blocker** | Check REC status.conditions for False conditions with messages | Fix the condition (e.g. storage, resources, API reachability) |
| **StatefulSet replicas = 1** | Check StatefulSet spec.replicas | Operator hasn't scaled yet; fix blockers (rec:9443, conditions) |
| **rec-1/rec-2 Pending** | Pods exist but Status = Pending | Check Events: PVC, quotas, node selector/taints |
| **Argo CD overwriting StatefulSet** | Argo CD shows StatefulSet OutOfSync with replicas: 1 | Remove StatefulSet from Git or add ignoreDifferences |

---

## Diagnostic Checklist

Run these checks **in order**:

- [ ] **StatefulSet replicas** = ? (1 or 3?)
- [ ] **REC status.nodes** = ? (1 or 3?)
- [ ] **REC status.readyNodes** = ? (1 or 3?)
- [ ] **REC status.state** = ? ("running", "creating", "scaling"?)
- [ ] **REC status.conditions** = ? (Any False conditions with messages?)
- [ ] **Operator logs** = ? (Any errors about rec:9443, scaling, or conditions?)
- [ ] **rec-services-rigger logs** = ? (Any timeout to rec:9443?)
- [ ] **rec-1/rec-2 pods exist?** (If yes, are they Pending? Check Events)
- [ ] **Argo CD StatefulSet sync** = ? (Is it overwriting replicas?)

---

## Most Likely Scenario

Based on your symptoms (rec-0 Running/Ready, service ready, but no rec-1/rec-2):

1. **StatefulSet replicas = 1** (operator hasn't scaled yet)
2. **REC status.nodes = 1** (operator thinks only 1 node should exist)
3. **Operator logs show**: "waiting for cluster API" or "RS API not available"
4. **rec-services-rigger logs show**: timeout to rec:9443

**Fix:** Create NetworkPolicies allowing traffic to REC pods on 9443 from rec-services-rigger and operator. Restart rec-services-rigger. Wait a few minutes. Operator should then scale to 3 nodes.

---

## Next Steps

1. Run the diagnostic checklist above.
2. Share the findings (StatefulSet replicas, REC status, operator logs).
3. Apply the fix based on the root cause identified.
4. Monitor operator logs and REC status until rec-1 and rec-2 are created.
