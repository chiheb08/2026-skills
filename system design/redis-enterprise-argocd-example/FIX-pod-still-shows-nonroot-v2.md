# Fix: Pod Still Shows `openshift.io/scc: nonroot-v2` Instead of `redis-enterprise-scc-v2`

**Problem:** After applying RoleBinding or other methods, your pod still shows `openshift.io/scc: nonroot-v2` instead of `redis-enterprise-scc-v2`.

---

## Why This Happens

OpenShift chooses the SCC for a pod based on:
1. **Which SCCs the ServiceAccount is allowed to use**
2. **Which SCCs match the pod's security requirements**
3. **OpenShift picks the most restrictive SCC** that still allows the pod to run

If your pod still shows `nonroot-v2`, it means:
- Either `redis-enterprise-scc-v2` is not granted to your ServiceAccount
- Or OpenShift is choosing `nonroot-v2` because it's more restrictive and still works

---

## Solution: Grant SCC Directly (Not RoleBinding)

**Important:** RoleBinding might not work for SCCs in all OpenShift versions. The **reliable way** is to **directly add your ServiceAccount to the SCC's `users` list**.

### Method 1: OpenShift UI (Recommended if you have access)

1. **Go to Administration → Security Context Constraints**
2. **Find and open `redis-enterprise-scc-v2`**
3. **Go to YAML tab**
4. **Find the `users` section** (or add it if it doesn't exist)
5. **Add your ServiceAccount** in this format:
   ```yaml
   users:
     - system:serviceaccount:<namespace>:<service-account-name>
   ```
   **Example:** If namespace is `redis-enterprise` and ServiceAccount is `rec`:
   ```yaml
   users:
     - system:serviceaccount:redis-enterprise:rec
   ```
6. **Click Save**

**If you don't have permission to save:** Ask your platform/security team to add the ServiceAccount to the SCC.

---

### Method 2: Manifest File (Direct SCC Modification)

Create a file `redis-enterprise-scc-users.yaml`:

```yaml
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: redis-enterprise-scc-v2
users:
  - system:serviceaccount:redis-enterprise:rec  # TODO: Replace with your namespace:serviceaccount
```

**Important:** 
- Replace `redis-enterprise:rec` with your actual `namespace:serviceaccount`
- This modifies the SCC directly (cluster-scoped resource)
- Requires **cluster-admin** permissions
- If you don't have cluster-admin, ask your platform team to apply this

**Apply via ArgoCD:**
- Add to your Git repo
- ArgoCD will sync it (if you have cluster-admin permissions)
- Or ask platform team to apply it manually

---

### Method 3: Check What SCCs Are Available to Your ServiceAccount

**In OpenShift UI:**

1. Go to **User Management** → **ServiceAccounts**
2. Find your ServiceAccount (e.g., `rec`)
3. Open it → **YAML** tab
4. Look for annotations or check which SCCs are granted

**Or check via terminal (if you have access):**

```bash
# Check which SCCs are granted to your ServiceAccount
oc get scc redis-enterprise-scc-v2 -o yaml | grep -A 10 "users:"

# Check what SCC your pod is using
oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}' && echo
```

---

## Troubleshooting Steps

### Step 1: Verify SCC Exists

```bash
# Check if SCC exists
oc get scc redis-enterprise-scc-v2
```

**If it doesn't exist:** The SCC needs to be created first (usually done by Redis Enterprise Operator installation).

### Step 2: Verify ServiceAccount Name

**In OpenShift UI:**
1. Go to **Workloads** → **Pods**
2. Open **rec-0**
3. **Details** tab → Look for **Service Account**

**Or check REC spec:**
- The ServiceAccount name usually matches your REC name (e.g., if REC is `rec`, ServiceAccount is `rec`)

### Step 3: Check Current SCC Users

**In OpenShift UI:**
1. Go to **Administration** → **Security Context Constraints**
2. Open **`redis-enterprise-scc-v2`**
3. **YAML** tab → Look at `users:` section
4. Check if your ServiceAccount is listed

**Format should be:**
```yaml
users:
  - system:serviceaccount:<namespace>:<service-account-name>
```

### Step 4: Add ServiceAccount to SCC

**If your ServiceAccount is NOT in the list:**

**Option A: Via UI (if you have permissions)**
- Edit the SCC YAML → Add your ServiceAccount to `users:` → Save

**Option B: Via Manifest (if you have cluster-admin)**
- Create manifest with SCC + users list → Apply via ArgoCD or kubectl

**Option C: Ask Platform Team**
- Provide them with: `system:serviceaccount:<namespace>:<service-account-name>`
- Ask them to add it to `redis-enterprise-scc-v2` SCC's users list

### Step 5: Restart Pods

After adding ServiceAccount to SCC:

```bash
# Restart pods
kubectl delete pod rec-0 rec-1 rec-2 -n <namespace>
```

**Or via OpenShift UI:**
- **Workloads** → **Pods** → Select all REC pods → **Actions** → **Delete**

### Step 6: Verify SCC Changed

**Check pod annotation:**

```bash
oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}' && echo
```

**Should show:** `redis-enterprise-scc-v2` (not `nonroot-v2`)

**Or in OpenShift UI:**
- **Workloads** → **Pods** → **rec-0** → **YAML** tab → Look for `metadata.annotations.openshift.io/scc`

---

## Why RoleBinding Might Not Work

**RoleBinding approach** (using `system:openshift:scc:redis-enterprise-scc-v2` ClusterRole) might not work because:

1. **SCCs are evaluated differently** - OpenShift checks the SCC's `users` list directly, not just RBAC
2. **OpenShift version differences** - Some versions might not support RoleBinding for SCCs
3. **Priority system** - OpenShift might still choose `nonroot-v2` if it's also granted and is more restrictive

**The reliable method is direct SCC modification** - adding ServiceAccount directly to the SCC's `users` list.

---

## Quick Fix Summary

**What to do:**

1. **Find your ServiceAccount name** (e.g., `rec`)
2. **Find your namespace** (e.g., `redis-enterprise`)
3. **Add to SCC directly:**
   - **Via UI:** Administration → SCCs → `redis-enterprise-scc-v2` → YAML → Add to `users:`
   - **Via Manifest:** Create SCC manifest with `users:` list → Apply
   - **Or ask platform team** to add: `system:serviceaccount:redis-enterprise:rec`
4. **Restart pods**
5. **Verify:** Pod should show `openshift.io/scc: redis-enterprise-scc-v2`

---

## Manifest File for Direct SCC Modification

Create `redis-enterprise-scc-grant.yaml`:

```yaml
# Direct SCC modification - adds ServiceAccount to SCC users list
# This is the RELIABLE way to grant SCCs (not RoleBinding)
#
# Usage:
# 1. Replace redis-enterprise:rec with your namespace:serviceaccount
# 2. Apply via ArgoCD or kubectl (requires cluster-admin)
# 3. If you don't have cluster-admin, ask platform team to apply this

apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: redis-enterprise-scc-v2
users:
  - system:serviceaccount:redis-enterprise:rec  # TODO: Replace with your namespace:serviceaccount
```

**Note:** This manifest **modifies** the existing SCC (doesn't create a new one). It adds your ServiceAccount to the `users` list.

**If you have multiple ServiceAccounts**, add them all:

```yaml
users:
  - system:serviceaccount:redis-enterprise:rec
  - system:serviceaccount:redis-enterprise:another-sa  # If you have multiple
```

---

## Still Not Working?

**Check these:**

1. **Is `redis-enterprise-scc-v2` SCC installed?**
   - Check: `oc get scc redis-enterprise-scc-v2`
   - If not, install it first (see BEST-SECURITY-POLICY-REC-OpenShift.md)

2. **Is ServiceAccount name correct?**
   - Verify: `kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}'`

3. **Is namespace correct?**
   - Verify: Check pod namespace matches SCC users entry

4. **Are pods restarted?**
   - SCC changes only apply to NEW pods, not existing ones

5. **Do you have permissions?**
   - SCC modifications require cluster-admin
   - If not, ask platform team to add ServiceAccount to SCC

---

## Summary

**The issue:** RoleBinding might not work for SCCs. You need to **directly modify the SCC** by adding your ServiceAccount to its `users` list.

**The fix:**
1. Add `system:serviceaccount:<namespace>:<sa-name>` to `redis-enterprise-scc-v2` SCC's `users` list
2. Restart pods
3. Verify pod shows `redis-enterprise-scc-v2` (not `nonroot-v2`)
