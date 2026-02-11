# Fix: pdns_server Exit Status 126 (Cannot Execute)

**Symptom:** `pdns_server (exit status 126; not expected)` in REC pod logs. Pods stuck in bootstrap.

**Exit status 126** means: **"Command invoked cannot execute"** — the executable cannot be run.

---

## Understanding Exit Status 126

Exit status 126 typically indicates:
- **Missing execute permissions** on the binary
- **Executable file missing or corrupted**
- **Library dependency missing** (shared library not found)
- **Security Context Constraints (SCC)** blocking execution in OpenShift
- **File system permissions** preventing execution

**pdns_server** is a PowerDNS server component used by Redis Enterprise for DNS resolution within the cluster.

---

## Step 1: Check Pod Logs for More Details

The logs might show more context about why pdns_server cannot execute.

### In OpenShift UI:

1. Go to **Workloads** → **Pods**.
2. Open **rec-0** (or the pod showing the error).
3. Go to **Logs** tab.
4. **Scroll up** from "exited: pdns_server" to find:
   - **"Permission denied"** → Execute permissions issue
   - **"No such file or directory"** → Executable missing
   - **"cannot open shared object file"** → Library dependency missing
   - **"Operation not permitted"** → SCC blocking execution

### With kubectl:

```bash
# Check rec-0 logs
kubectl logs rec-0 -n <namespace> --tail=200 | grep -A 5 -B 5 "pdns_server\|126\|permission\|cannot execute"
```

---

## Step 2: Check Security Context Constraints (SCC) in OpenShift

**Most common cause in OpenShift:** SCC is blocking execution or requiring specific permissions.

### Check Pod Security Context:

```bash
# Check pod security context
kubectl get pod rec-0 -n <namespace> -o yaml | grep -A 20 "securityContext:"

# Check if pod is running as non-root or with restricted permissions
kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.securityContext}' | jq
```

### Check SCC Applied to Pod:

```bash
# Check which SCC is applied (OpenShift specific)
oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}' && echo
```

**Common SCC issues:**
- **restricted-v2** or **restricted** SCC → May block execution of binaries
- **nonroot** SCC → May require specific user/group permissions
- **anyuid** SCC → Usually allows execution (if available)

---

## Step 3: Check Container Image and Executable

The pdns_server executable might be missing or corrupted in the container image.

### Check if Executable Exists:

```bash
# Exec into pod and check if pdns_server exists
kubectl exec -it rec-0 -n <namespace> -- ls -la /opt/redislabs/bin/pdns_server

# Or check common locations
kubectl exec -it rec-0 -n <namespace> -- find / -name pdns_server 2>/dev/null
```

**If executable is missing:** Container image issue → Check image version, pull image again.

### Check Execute Permissions:

```bash
# Check file permissions
kubectl exec -it rec-0 -n <namespace> -- ls -la /opt/redislabs/bin/pdns_server

# Should show: -rwxr-xr-x or similar (x = execute permission)
# If missing x: chmod +x /opt/redislabs/bin/pdns_server (but this won't persist)
```

---

## Step 4: Check Library Dependencies

pdns_server might be missing required shared libraries.

### Check Library Dependencies:

```bash
# Check what libraries pdns_server needs
kubectl exec -it rec-0 -n <namespace> -- ldd /opt/redislabs/bin/pdns_server

# Look for "not found" libraries
```

**If libraries are missing:** Container image issue or base image problem.

---

## Step 5: Check Pod Security Context in REC Spec

The REC spec might be setting a security context that prevents execution.

### Check REC Spec:

```bash
# Check REC spec for securityContext
kubectl get rec <rec-name> -n <namespace> -o yaml | grep -A 30 "securityContext:"
```

**Look for:**
- `runAsNonRoot: true` → Might need `runAsUser` set appropriately
- `readOnlyRootFilesystem: true` → Might prevent execution
- `allowPrivilegeEscalation: false` → Usually OK, but check

---

## Step 6: Check OpenShift SCC Configuration

In OpenShift, you may need to adjust SCC or use a different one.

### List Available SCCs:

```bash
# List SCCs
oc get scc

# Check which SCC allows execution
oc describe scc restricted-v2
oc describe scc anyuid
```

### Check ServiceAccount:

```bash
# Check which ServiceAccount the pod uses
kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}' && echo

# Check SCC bound to ServiceAccount
oc get sa <service-account-name> -n <namespace> -o yaml | grep scc
```

---

## Common Root Causes and Fixes

| Root Cause | Symptoms | Fix |
|------------|----------|-----|
| **SCC blocking execution** | "Operation not permitted", "Permission denied" | Use `anyuid` SCC or adjust SCC to allow execution |
| **Missing execute permissions** | "Permission denied" on pdns_server | Check file permissions, ensure executable bit is set (image issue) |
| **Executable missing** | "No such file or directory" | Check container image, pull image again, verify image version |
| **Library dependency missing** | "cannot open shared object file" | Check base image, ensure all libraries are present |
| **Security context too restrictive** | `runAsNonRoot` or `readOnlyRootFilesystem` blocking | Adjust security context in REC spec or SCC |

---

## Fix: Use anyuid SCC (OpenShift)

If SCC is blocking execution, use `anyuid` SCC (if available and allowed by your security policy).

### Option 1: Add anyuid SCC to ServiceAccount

```bash
# Find the ServiceAccount used by REC pods
kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}' && echo

# Add anyuid SCC to ServiceAccount (replace <sa-name>)
oc adm policy add-scc-to-user anyuid -z <sa-name> -n <namespace>
```

### Option 2: Use anyuid SCC in REC Spec

If the REC spec allows, you can specify SCC in annotations (OpenShift-specific):

```yaml
apiVersion: app.redislabs.com/v1
kind: RedisEnterpriseCluster
metadata:
  name: rec
  namespace: redis-enterprise
  annotations:
    openshift.io/scc: anyuid  # Use anyuid SCC
spec:
  # ... rest of spec
```

**Note:** `anyuid` allows running as any user, which may not be allowed by your security policy. Check with your platform team.

---

## Fix: Check Container Image

If the executable is missing or corrupted:

### Verify Image:

```bash
# Check image used by pod
kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.containers[0].image}' && echo

# Pull image and verify
docker pull <image-name>
docker run --rm <image-name> ls -la /opt/redislabs/bin/pdns_server
```

**If image is corrupted:** Pull fresh image, or check if image version is correct.

---

## Fix: Adjust Security Context

If security context is too restrictive:

### Check Current Security Context:

```bash
kubectl get pod rec-0 -n <namespace> -o yaml | grep -A 20 "securityContext:"
```

### Adjust in REC Spec (if supported):

Some REC specs allow security context configuration. Check Redis Enterprise Operator documentation for your version.

---

## Diagnostic Checklist

Run these checks **in order**:

- [ ] **Check pod logs** → Find actual error message (permission denied, missing file, etc.)
- [ ] **Check SCC** → Which SCC is applied? Is it blocking execution?
- [ ] **Check executable exists** → `kubectl exec -it rec-0 -- ls -la /opt/redislabs/bin/pdns_server`
- [ ] **Check file permissions** → Ensure executable bit is set
- [ ] **Check library dependencies** → `ldd` on pdns_server
- [ ] **Check security context** → Pod and REC spec security context
- [ ] **Check ServiceAccount** → Which SCC is bound to it?

---

## Most Likely Fix

**In OpenShift, SCC is blocking execution.**

**Steps:**

1. **Check which SCC is applied:**
   ```bash
   oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}' && echo
   ```

2. **If SCC is `restricted-v2` or `restricted`:**
   - Use `anyuid` SCC (if allowed by security policy)
   - Or adjust SCC to allow execution

3. **Add anyuid SCC to ServiceAccount:**
   ```bash
   # Find ServiceAccount
   SA=$(kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}')
   
   # Add anyuid SCC
   oc adm policy add-scc-to-user anyuid -z $SA -n <namespace>
   ```

4. **Restart pods:**
   ```bash
   kubectl delete pod rec-0 rec-1 rec-2 -n <namespace>
   ```

---

## Next Steps

1. **Check pod logs** → Find the exact error (permission denied, missing file, etc.)
2. **Check SCC** → Which SCC is applied? Is it `restricted-v2`?
3. **Try anyuid SCC** → If allowed, add it to ServiceAccount
4. **Restart pods** → After fixing SCC

**Share:**
- The exact error message from logs (scroll up from "exited: pdns_server")
- Which SCC is applied to the pod
- Whether you can use `anyuid` SCC (check with platform team if unsure)

The most common cause in OpenShift is **SCC blocking execution**. Using `anyuid` SCC usually fixes this, but check your security policy first.
