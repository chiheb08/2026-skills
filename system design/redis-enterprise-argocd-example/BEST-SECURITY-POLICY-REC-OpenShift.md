# Best Security Policy for Redis Enterprise Cluster on OpenShift

**Research Summary:** Based on official Redis Enterprise documentation and OpenShift security best practices, the **recommended security policy is NOT `anyuid`**, but rather the **official `redis-enterprise-scc-v2` Security Context Constraint (SCC)**.

---

## Executive Summary

| Option | Security Level | Recommendation |
|--------|----------------|---------------|
| **`redis-enterprise-scc-v2`** (Official) | ✅ **High** - Same as restricted-v2 with minimal exceptions | **✅ RECOMMENDED** |
| **`anyuid`** | ⚠️ **Low** - Allows root, very permissive | ❌ Not recommended (workaround only) |
| **`nonroot-v2`** | ✅ **High** - But too restrictive for REC | ❌ Blocks required components |
| **`restricted-v2`** | ✅ **High** - But too restrictive for REC | ❌ Blocks required components |

---

## The Official Solution: `redis-enterprise-scc-v2` SCC

### What is `redis-enterprise-scc-v2`?

**`redis-enterprise-scc-v2`** is a **custom SCC provided by Redis Enterprise** specifically designed for OpenShift deployments. It provides:

- ✅ **Same security level as `restricted-v2`** (high security)
- ✅ **Minimal exceptions** only for what Redis Enterprise actually needs
- ✅ **Runs as UID/GID 1001** (non-root user)
- ✅ **No root access** (unlike `anyuid`)
- ✅ **Specific capabilities only** (`SYS_RESOURCE` for file descriptor limits)

### Why `redis-enterprise-scc-v2` is Better Than `anyuid`

| Feature | `redis-enterprise-scc-v2` | `anyuid` |
|---------|---------------------------|----------|
| **Runs as root?** | ❌ No (runs as UID 1001) | ✅ Yes (allows any UID including root) |
| **Security level** | ✅ High (restricted-v2 equivalent) | ⚠️ Low (very permissive) |
| **Capabilities** | ✅ Only `SYS_RESOURCE` (minimal) | ⚠️ All capabilities allowed |
| **Host access** | ❌ No | ⚠️ Depends on configuration |
| **Official support** | ✅ Yes (Redis Enterprise official) | ❌ No (generic OpenShift SCC) |
| **Security compliance** | ✅ Meets enterprise security standards | ⚠️ May violate security policies |

---

## How to Use `redis-enterprise-scc-v2`

**Choose your method:**
- **Method 1: OpenShift UI** (if you don't have terminal access) → See section below
- **Method 2: Manifest file + ArgoCD** (GitOps approach) → See section below
- **Method 3: Terminal/CLI** (if you have access) → See section below

---

## Method 1: Using OpenShift UI (No Terminal Required)

This method uses the OpenShift Web Console UI, so you don't need terminal/CLI access.

### Step 1: Verify the SCC Exists

1. Log in to **OpenShift Web Console**
2. Go to **Administration** → **Cluster Settings** → **Security Context Constraints** (or search for "SCC" in the search bar)
3. Look for **`redis-enterprise-scc-v2`** in the list
4. If it exists → proceed to Step 2
5. If it doesn't exist → see "If SCC doesn't exist" section below

### Step 2: Find Your REC ServiceAccount

1. Go to **Workloads** → **Pods**
2. Find and open your **rec-0** pod
3. Go to the **Details** tab or **YAML** tab
4. Look for **Service Account** field (or `spec.serviceAccountName` in YAML)
5. **Note down the ServiceAccount name** (e.g., `rec` or `default`)

### Step 3: Grant SCC to ServiceAccount via UI

**Option A: Using RBAC (RoleBinding) - Recommended**

1. Go to **User Management** → **RoleBindings** (or search for "RoleBinding")
2. Click **Create RoleBinding**
3. Fill in:
   - **Name:** `redis-enterprise-scc-binding` (or any name you prefer)
   - **Namespace:** Select your REC namespace (e.g., `redis-enterprise`)
   - **Role name:** Leave empty or use a custom role
   - **Subject kind:** Select **ServiceAccount**
   - **Subject name:** Enter your ServiceAccount name from Step 2 (e.g., `rec`)
   - **Subject namespace:** Select your REC namespace

**Note:** The UI method for directly adding SCC to ServiceAccount is limited. You may need to use **Option B** (YAML view) or **Method 2** (Manifest file).

**Option B: Using YAML View (Easier - Recommended)**

1. Go to **Administration** → **Security Context Constraints** (or search for "SCC" in the search bar)
2. Find and open **`redis-enterprise-scc-v2`**
3. Go to **YAML** tab
4. Find the **`users`** section (or add it if it doesn't exist)
5. Add your ServiceAccount in this format:
   ```yaml
   users:
     - system:serviceaccount:<namespace>:<service-account-name>
   ```
   **Example:** If namespace is `redis-enterprise` and ServiceAccount is `rec`:
   ```yaml
   users:
     - system:serviceaccount:redis-enterprise:rec
   ```
6. Click **Save**

**Note:** If you don't see the **Save** button or get a permission error, you may need cluster-admin permissions. In that case, ask your platform/security team to add the ServiceAccount to the SCC, or use **Method 2 (ArgoCD)** if you have Git access.

### Step 4: Restart REC Pods

1. Go to **Workloads** → **Pods**
2. Select **rec-0**, **rec-1**, **rec-2** (or all REC pods)
3. Click **Actions** → **Delete** (or use the trash icon)
4. Confirm deletion
5. Pods will be recreated automatically with the new SCC

### Step 5: Verify SCC is Applied

1. Go to **Workloads** → **Pods**
2. Open **rec-0** pod
3. Go to **YAML** tab
4. Look for `metadata.annotations.openshift.io/scc`
5. It should show: **`redis-enterprise-scc-v2`**

---

## Method 2: Using Manifest File + ArgoCD (GitOps)

This method allows you to manage SCC grants through Git and ArgoCD, following GitOps best practices.

### Step 1: Create RoleBinding Manifest

**A ready-to-use manifest file is available:** `redis-enterprise-scc-binding.yaml` in this repository.

**Or create your own file** named `redis-enterprise-scc-binding.yaml`:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: redis-enterprise-scc-binding
  namespace: redis-enterprise  # Replace with your namespace
  annotations:
    argocd.argoproj.io/sync-wave: "0"  # Apply before REC
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:openshift:scc:redis-enterprise-scc-v2
subjects:
  - kind: ServiceAccount
    name: rec  # Replace with your ServiceAccount name
    namespace: redis-enterprise  # Replace with your namespace
```

**Important:** Replace:
- `namespace: redis-enterprise` → Your actual namespace
- `name: rec` → Your actual ServiceAccount name

**To find your ServiceAccount name:**
- OpenShift UI: **Workloads** → **Pods** → **rec-0** → **Details** tab → Look for **Service Account**
- Or check REC spec if you set it explicitly

### Step 2: Alternative - Direct SCC User Addition (Cluster-level)

**⚠️ Important:** This method requires **cluster-admin** permissions and may not work through ArgoCD if you don't have cluster-level access. **Check with your platform/security team first.**

If the RoleBinding approach doesn't work, you can create a manifest that directly modifies the SCC:

Create `redis-enterprise-scc-patch.yaml`:

```yaml
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: redis-enterprise-scc-v2
users:
  - system:serviceaccount:redis-enterprise:rec  # Replace with your namespace:serviceaccount
```

**Apply via ArgoCD:**
- Add this file to your Git repository
- ArgoCD will sync it (if you have permissions to modify SCCs)
- **Note:** SCC modifications are cluster-scoped and typically require cluster-admin permissions

**If you don't have cluster-admin access:**
- Use **Method 1 (OpenShift UI)** and ask your platform team to grant the SCC
- Or ask your platform team to apply the RoleBinding or SCC modification for you

### Step 3: Add to ArgoCD Application

**Option A: Add to existing REC application**

1. Add `redis-enterprise-scc-binding.yaml` to the same directory as your `rec.yaml`
2. ArgoCD will automatically sync it

**Option B: Create separate ArgoCD application**

Create `redis-enterprise-scc-application.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: redis-enterprise-scc
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/your-repo.git  # Replace with your repo
    targetRevision: main
    path: system design/redis-enterprise-argocd-example  # Path to your manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: redis-enterprise  # Replace with your namespace
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### Step 4: Verify in ArgoCD

1. Open ArgoCD UI
2. Check your application shows **Synced** and **Healthy**
3. Verify the RoleBinding exists:
   - In OpenShift UI: **User Management** → **RoleBindings** → Look for `redis-enterprise-scc-binding`

### Step 5: Restart REC Pods

After ArgoCD syncs the RoleBinding, restart REC pods (via OpenShift UI or ArgoCD sync):

**Via OpenShift UI:**
1. **Workloads** → **Pods** → Select rec-0, rec-1, rec-2 → **Actions** → **Delete**

**Via ArgoCD:**
1. Open your REC application
2. Click **Sync** → **Synchronize** (this will recreate pods if needed)

---

## Method 3: Using Terminal/CLI (If You Have Access)

### Step 1: Verify the SCC Exists

The `redis-enterprise-scc-v2` SCC should be created automatically when you install the Redis Enterprise Operator. Verify it exists:

```bash
oc get scc redis-enterprise-scc-v2
```

**If it doesn't exist:** The SCC is typically created by the Redis Enterprise Operator installation. Check your operator installation.

**If you need to create it manually**, here's the official SCC YAML from Redis Enterprise documentation:

```yaml
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: redis-enterprise-scc-v2
  annotations:
    kubernetes.io/description: redis-enterprise-scc-v2 is the minimal SCC needed to run Redis Enterprise nodes on Kubernetes with automatic FD limit adjustment enabled. It provides the same features as restricted-v2 SCC, but allows pods to enable the SYS_RESOURCE capability, which is required by Redis Enterprise nodes to manage file descriptor limits and OOM scores for database shards. Additionally, it requires pods to run as UID/GID 1001, which are the UID/GID used within the Redis Enterprise node containers.
allowedCapabilities:
  - SYS_RESOURCE
allowHostDirVolumePlugin: false
allowHostIPC: false
allowHostNetwork: false
allowHostPID: false
allowHostPorts: false
allowPrivilegeEscalation: true
allowPrivilegedContainer: false
readOnlyRootFilesystem: false
runAsUser:
  type: MustRunAs
  uid: 1001
fsGroup:
  type: MustRunAs
  ranges:
    - min: 1001
      max: 1001
seLinuxContext:
  type: MustRunAs
seccompProfiles:
  - runtime/default
supplementalGroups:
  type: RunAsAny
```

Apply it with:
```bash
oc apply -f redis-enterprise-scc-v2.yaml
```

### Step 2: Find Your REC ServiceAccount

```bash
# Find the ServiceAccount used by REC pods
kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}' && echo
```

**Common names:** Usually matches your REC name (e.g., if REC is named `rec`, ServiceAccount is `rec`).

### Step 3: Grant `redis-enterprise-scc-v2` to ServiceAccount

```bash
# Replace <namespace> with your namespace
# Replace <sa-name> with ServiceAccount name from Step 2
oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:<namespace>:<sa-name>
```

**Example:**
```bash
# If REC is named "rec" in namespace "redis-enterprise"
oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:redis-enterprise:rec
```

### Step 4: Restart REC Pods

```bash
kubectl delete pod rec-0 rec-1 rec-2 -n <namespace>
```

After restart, pods should use `redis-enterprise-scc-v2` and run successfully.

---

## What `redis-enterprise-scc-v2` Allows

Based on official Redis Enterprise documentation, `redis-enterprise-scc-v2` provides:

### Allowed Capabilities
- **`SYS_RESOURCE`** — Required for Redis Enterprise to manage file descriptor limits and OOM scores for database shards

### User/Group Requirements
- **UID/GID 1001** — Standard UID/GID used in Redis Enterprise node containers (non-root)

### Privilege Settings
- **`allowPrivilegeEscalation: true`** — Required for Redis Enterprise operations
- **Privileged containers:** ❌ Disabled (more secure)

### Host Access
- **Host directory volumes:** ❌ Disallowed
- **Host IPC:** ❌ Disallowed
- **Host network:** ❌ Disallowed
- **Host PID:** ❌ Disallowed
- **Host ports:** ❌ Disallowed

### Other Settings
- **Read-only root filesystem:** Disabled (Redis Enterprise needs write access)
- **SELinux:** Must run as specified

---

## Automatic Resource Adjustment (Version 7.22.0-6+)

**Important:** For Redis Enterprise Operator version **7.22.0-6 and later**, automatic resource adjustment is **disabled by default** for enhanced security.

### When Disabled (Default - More Secure)
- All capabilities are dropped
- `allowPrivilegeEscalation: false`
- No elevated permissions

### When Enabled (If Needed)
If file descriptor limits are suspected to be below 100,000, you can enable automatic resource adjustment:

```yaml
apiVersion: app.redislabs.com/v1
kind: RedisEnterpriseCluster
metadata:
  name: rec
  namespace: redis-enterprise
spec:
  allowAutoAdjustment: true  # Enable automatic resource adjustment
  nodes: 3
  # ... rest of spec
```

**Note:** Most cloud providers and standard configurations have sufficient file descriptor limits, so this may not be necessary.

---

## Comparison: Security Policies

### 1. `redis-enterprise-scc-v2` (✅ RECOMMENDED)

**Security Level:** High (restricted-v2 equivalent)

**Pros:**
- ✅ Official Redis Enterprise SCC
- ✅ Non-root (UID 1001)
- ✅ Minimal capabilities (only SYS_RESOURCE)
- ✅ No host access
- ✅ Meets enterprise security standards
- ✅ Designed specifically for Redis Enterprise

**Cons:**
- ⚠️ Requires SCC to be installed (usually automatic with operator)

**Use when:** ✅ **Always** — This is the official, secure solution.

---

### 2. `anyuid` (❌ NOT RECOMMENDED)

**Security Level:** Low

**Pros:**
- ✅ Works (allows execution)
- ✅ Simple to apply

**Cons:**
- ❌ Allows root access
- ❌ Very permissive (security risk)
- ❌ May violate security policies
- ❌ Not officially supported by Redis Enterprise
- ❌ Not designed for Redis Enterprise

**Use when:** ⚠️ **Only as a temporary workaround** if `redis-enterprise-scc-v2` is not available and you need immediate functionality. **Should be replaced with `redis-enterprise-scc-v2` ASAP.**

---

### 3. `nonroot-v2` (❌ TOO RESTRICTIVE)

**Security Level:** High

**Pros:**
- ✅ Non-root (secure)
- ✅ Restrictive (good for security)

**Cons:**
- ❌ Too restrictive for Redis Enterprise
- ❌ Blocks `pdns_server` and other components (exit 126)
- ❌ Cannot complete bootstrap

**Use when:** ❌ **Never** — Too restrictive for Redis Enterprise.

---

### 4. `restricted-v2` (❌ TOO RESTRICTIVE)

**Security Level:** High

**Pros:**
- ✅ Very secure
- ✅ Standard OpenShift SCC

**Cons:**
- ❌ Too restrictive for Redis Enterprise
- ❌ Blocks required components
- ❌ Cannot complete bootstrap

**Use when:** ❌ **Never** — Too restrictive for Redis Enterprise.

---

## Security Best Practices Summary

### ✅ DO

1. **Use `redis-enterprise-scc-v2`** — Official, secure SCC designed for Redis Enterprise
2. **Run as non-root** — `redis-enterprise-scc-v2` uses UID 1001 (not root)
3. **Minimal capabilities** — Only `SYS_RESOURCE` (what Redis Enterprise actually needs)
4. **Network isolation** — Use NetworkPolicies to restrict traffic
5. **RBAC** — Use proper Role-Based Access Control
6. **Secrets management** — Store credentials in Kubernetes Secrets
7. **TLS encryption** — Enable TLS for cluster and client connections
8. **Namespace isolation** — Run REC in dedicated namespace

### ❌ DON'T

1. **Don't use `anyuid`** — Too permissive, security risk
2. **Don't run as root** — Security vulnerability
3. **Don't grant unnecessary capabilities** — Principle of least privilege
4. **Don't skip NetworkPolicies** — Network isolation is critical
5. **Don't use default SCCs** — They're too restrictive or too permissive

---

## Troubleshooting: If `redis-enterprise-scc-v2` Doesn't Work

### Issue: SCC doesn't exist

**Solution:** The SCC should be created automatically by the Redis Enterprise Operator. If it doesn't exist:

1. Check operator installation: `kubectl get deployment redis-enterprise-operator -n <operator-namespace>`
2. Check operator logs for SCC creation errors
3. Manually create SCC (see Redis Enterprise documentation for SCC YAML)

### Issue: Still getting exit 126

**Possible causes:**
1. **SCC not granted to ServiceAccount** — Verify with: `oc get scc redis-enterprise-scc-v2 -o yaml | grep -A 10 users`
2. **Wrong ServiceAccount** — Check pod ServiceAccount: `kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}'`
3. **SCC configuration issue** — Verify SCC allows required capabilities

### Issue: File descriptor limits too low

**Solution:** Enable automatic resource adjustment in REC spec:

```yaml
spec:
  allowAutoAdjustment: true
```

---

## Migration from `anyuid` to `redis-enterprise-scc-v2`

If you're currently using `anyuid` (workaround), migrate to `redis-enterprise-scc-v2`:

### Step 1: Verify `redis-enterprise-scc-v2` exists

```bash
oc get scc redis-enterprise-scc-v2
```

### Step 2: Grant `redis-enterprise-scc-v2` to ServiceAccount

```bash
oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:<namespace>:<sa-name>
```

### Step 3: Remove `anyuid` (optional but recommended)

```bash
oc adm policy remove-scc-from-user anyuid system:serviceaccount:<namespace>:<sa-name>
```

### Step 4: Restart pods

```bash
kubectl delete pod rec-0 rec-1 rec-2 -n <namespace>
```

### Step 5: Verify

```bash
# Check pod is using redis-enterprise-scc-v2
oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}' && echo

# Should show: redis-enterprise-scc-v2
```

---

## Conclusion

**The best security policy for Redis Enterprise Cluster on OpenShift is `redis-enterprise-scc-v2`.**

- ✅ **Secure** — Same security level as restricted-v2
- ✅ **Non-root** — Runs as UID 1001
- ✅ **Minimal permissions** — Only what Redis Enterprise needs
- ✅ **Official** — Supported by Redis Enterprise
- ✅ **Compliant** — Meets enterprise security standards

**Avoid `anyuid`** — It's a security risk and should only be used as a temporary workaround if `redis-enterprise-scc-v2` is not available.

---

## References

- [Redis Enterprise OpenShift SCC Documentation](https://redis.io/docs/latest/embeds/k8s/openshift_scc)
- [Redis Enterprise Security Documentation](https://redis.io/docs/latest/operate/kubernetes/security/)
- [Redis Enterprise OpenShift Deployment Guide](https://redis.io/docs/latest/operate/kubernetes/deployment/openshift/openshift-cli/)
