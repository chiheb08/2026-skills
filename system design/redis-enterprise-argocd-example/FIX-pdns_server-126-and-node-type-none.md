# Fix: pdns_server Exit 126 + "Node Type is None"

**Symptoms:**
- `pdns_server (exit status 126; not expected)` — repeatedly failing
- `gave up: pdns_server entered FATAL state, too many start retries too quickly`
- `Node Type is None` during bootstrapping
- Pods stuck in bootstrap

**Root Cause:** Exit status 126 = executable cannot run. In OpenShift, this is usually **Security Context Constraints (SCC)** blocking execution.

---

## Immediate Fix: Add anyuid SCC

### Step 1: Find ServiceAccount

```bash
# Find ServiceAccount used by REC pods
kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}' && echo
```

### Step 2: Check Current SCC

```bash
# Check which SCC is applied
oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}' && echo
```

**If it shows `restricted-v2` or `restricted`:** That's blocking execution.

### Step 3: Add anyuid SCC

```bash
# Replace <sa-name> with ServiceAccount from Step 1
# Replace <namespace> with your namespace
oc adm policy add-scc-to-user anyuid -z <sa-name> -n <namespace>
```

**Note:** Check with your platform team if `anyuid` SCC is allowed by your security policy.

### Step 4: Restart Pods

```bash
kubectl delete pod rec-0 rec-1 rec-2 -n <namespace>
```

After restart, `pdns_server` should execute successfully, and "Node Type is None" should resolve once bootstrap completes.

---

## Understanding "Node Type is None"

**"Node Type is None"** appears during bootstrapping when:
- The node hasn't determined its role yet (first node vs joining node)
- Bootstrap process hasn't completed
- Configuration isn't set correctly

**Why it happens:**
- `pdns_server` is failing → Bootstrap cannot complete → Node type never gets set
- Once `pdns_server` runs successfully, bootstrap completes → Node type gets set correctly

**Fix:** Fix `pdns_server` first (SCC issue), then bootstrap will complete and node type will be set.

---

## Alternative: Check if Executable Exists

If SCC fix doesn't work, verify the executable exists:

```bash
# Check if pdns_server exists
kubectl exec -it rec-0 -n <namespace> -- ls -la /opt/redislabs/bin/pdns_server

# Check file permissions
kubectl exec -it rec-0 -n <namespace> -- file /opt/redislabs/bin/pdns_server

# Check library dependencies
kubectl exec -it rec-0 -n <namespace> -- ldd /opt/redislabs/bin/pdns_server
```

**If executable is missing or corrupted:** Container image issue → Check image version, pull fresh image.

---

## Verify Fix

After applying SCC and restarting pods:

1. **Check pdns_server is running:**
   ```bash
   kubectl logs rec-0 -n <namespace> | grep pdns_server
   ```
   Should show: `INFO success: pdns_server entered RUNNING state` (not "exited")

2. **Check bootstrap completes:**
   ```bash
   kubectl logs rec-0 -n <namespace> | grep -i "bootstrap\|node type"
   ```
   Should show node type set correctly (not "None")

3. **Check pod becomes Ready:**
   ```bash
   kubectl get pod rec-0 -n <namespace>
   ```
   Should show **Ready = 2/2** (not 1/2)

---

## Summary

1. **Add anyuid SCC** to ServiceAccount → Fixes exit status 126
2. **Restart pods** → `pdns_server` should execute successfully
3. **Bootstrap completes** → Node type gets set correctly
4. **Pods become Ready** → rec-0, then rec-1, then rec-2

The "Node Type is None" issue will resolve automatically once `pdns_server` runs and bootstrap completes.
