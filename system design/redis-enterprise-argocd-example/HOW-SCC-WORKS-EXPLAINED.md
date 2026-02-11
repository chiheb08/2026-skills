# How SCCs Work in OpenShift - Explained Simply

This document explains how Security Context Constraints (SCCs) work and how to grant them to ServiceAccounts.

---

## Understanding the Components

### 1. **Security Context Constraint (SCC)**
- An **SCC** is a cluster-level resource that defines what a pod can do (which user it runs as, what capabilities it has, etc.)
- Example: `redis-enterprise-scc-v2` is an SCC
- SCCs have a **`users`** list that specifies which ServiceAccounts (or users) are allowed to use this SCC

### 2. **ServiceAccount**
- A **ServiceAccount** is an identity that pods use
- Example: Your REC pods use a ServiceAccount (e.g., `rec` or `default`)
- When a pod starts, OpenShift checks: "Does this ServiceAccount have permission to use an SCC?"

### 3. **RoleBinding**
- A **RoleBinding** connects a **Role** (or **ClusterRole**) to **subjects** (ServiceAccounts, users, groups)
- Think of it as: "This ServiceAccount can do what this Role allows"

### 4. **ClusterRole** (for SCCs)
- OpenShift automatically creates **ClusterRoles** for each SCC
- Format: `system:openshift:scc:<scc-name>`
- Example: `system:openshift:scc:redis-enterprise-scc-v2`
- This ClusterRole grants permission to use that specific SCC

---

## How SCCs Are Granted: Two Methods

### Method 1: Direct SCC Modification (Traditional Way)

**What happens:**
- You add the ServiceAccount directly to the SCC's `users` list
- Command: `oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:namespace:sa-name`
- This modifies the SCC resource itself

**Visual representation:**
```
SCC: redis-enterprise-scc-v2
  └─ users:
      └─ system:serviceaccount:redis-enterprise:rec  ← ServiceAccount added here
```

**Manifest approach:**
```yaml
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: redis-enterprise-scc-v2
users:
  - system:serviceaccount:redis-enterprise:rec  # Your ServiceAccount
```

**Pros:**
- ✅ Direct and simple
- ✅ Works reliably

**Cons:**
- ❌ Requires cluster-admin permissions (SCCs are cluster-scoped)
- ❌ May not work through ArgoCD if you don't have cluster-admin

---

### Method 2: RoleBinding with ClusterRole (RBAC Way)

**What happens:**
- OpenShift has a built-in ClusterRole: `system:openshift:scc:redis-enterprise-scc-v2`
- You create a RoleBinding that says: "This ServiceAccount can use this ClusterRole"
- The ClusterRole grants permission to use the SCC

**Visual representation:**
```
RoleBinding (namespace-scoped)
  ├─ roleRef:
  │   └─ ClusterRole: system:openshift:scc:redis-enterprise-scc-v2  ← Built-in by OpenShift
  └─ subjects:
      └─ ServiceAccount: rec  ← Your ServiceAccount
```

**Manifest:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: redis-enterprise-scc-binding
  namespace: redis-enterprise  # Your namespace
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:openshift:scc:redis-enterprise-scc-v2  # Built-in ClusterRole
subjects:
  - kind: ServiceAccount
    name: rec  # Your ServiceAccount
    namespace: redis-enterprise  # Your namespace
```

**Pros:**
- ✅ Uses standard Kubernetes RBAC (familiar pattern)
- ✅ Namespace-scoped (easier to manage)
- ✅ Can be deployed via ArgoCD (if you have RBAC permissions)

**Cons:**
- ⚠️ Requires the ClusterRole to exist (OpenShift creates it automatically, but verify)
- ⚠️ May not work if OpenShift version doesn't support this pattern

---

## Which Method Should You Use?

### Use Method 1 (Direct SCC Modification) if:
- ✅ You have cluster-admin permissions
- ✅ You can modify SCCs directly
- ✅ You want the simplest approach

### Use Method 2 (RoleBinding) if:
- ✅ You don't have cluster-admin permissions
- ✅ You want to manage via GitOps/ArgoCD
- ✅ You prefer RBAC patterns

### If Neither Works:
- Ask your platform/security team to grant the SCC for you
- They can use either method

---

## Step-by-Step: What You Need to Do

### For Method 1 (Direct SCC Modification):

**What you're doing:** Adding your ServiceAccount to the SCC's `users` list.

**Steps:**
1. Find your ServiceAccount name (e.g., `rec`)
2. Find your namespace (e.g., `redis-enterprise`)
3. Create a manifest that modifies the SCC:
   ```yaml
   apiVersion: security.openshift.io/v1
   kind: SecurityContextConstraints
   metadata:
     name: redis-enterprise-scc-v2
   users:
     - system:serviceaccount:redis-enterprise:rec
   ```
4. Apply it (requires cluster-admin)

**Who does what:**
- **You:** Create the manifest, commit to Git
- **Platform team (with cluster-admin):** Apply it, or ArgoCD applies it if you have permissions

---

### For Method 2 (RoleBinding):

**What you're doing:** Creating a RoleBinding that grants the built-in ClusterRole to your ServiceAccount.

**Steps:**
1. Find your ServiceAccount name (e.g., `rec`)
2. Find your namespace (e.g., `redis-enterprise`)
3. Create a RoleBinding manifest:
   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: RoleBinding
   metadata:
     name: redis-enterprise-scc-binding
     namespace: redis-enterprise
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: system:openshift:scc:redis-enterprise-scc-v2  # Built-in, you don't create this
   subjects:
     - kind: ServiceAccount
       name: rec
       namespace: redis-enterprise
   ```
4. Apply it via ArgoCD or kubectl

**Who does what:**
- **You:** Create the RoleBinding manifest, commit to Git, ArgoCD syncs it
- **OpenShift:** Provides the built-in ClusterRole automatically

---

## Common Questions

### Q: Do I need to create the ClusterRole?

**A:** No! OpenShift creates it automatically. When an SCC exists (like `redis-enterprise-scc-v2`), OpenShift automatically creates a ClusterRole named `system:openshift:scc:redis-enterprise-scc-v2`. You just reference it in your RoleBinding.

### Q: Do I need to create a Role?

**A:** No! You're using a **ClusterRole** (cluster-scoped role), not a Role (namespace-scoped). The ClusterRole is built-in by OpenShift.

### Q: What does the RoleBinding do?

**A:** The RoleBinding says: "The ServiceAccount `rec` in namespace `redis-enterprise` can use the ClusterRole `system:openshift:scc:redis-enterprise-scc-v2`", which grants permission to use the `redis-enterprise-scc-v2` SCC.

### Q: Which method is better?

**A:** 
- **Method 1** is simpler and more direct
- **Method 2** is better for GitOps and if you don't have cluster-admin
- Both achieve the same result: allowing your ServiceAccount to use the SCC

### Q: How do I verify it worked?

**A:** After applying either method:
1. Restart your REC pods
2. Check pod annotations: `oc get pod rec-0 -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}'`
3. Should show: `redis-enterprise-scc-v2`

---

## Summary

| Component | What It Is | Who Creates It |
|-----------|------------|----------------|
| **SCC** | Security rules for pods | Redis Enterprise Operator (or you manually) |
| **ServiceAccount** | Identity for pods | You (or operator creates it) |
| **ClusterRole** | Permission to use SCC | OpenShift (automatic, built-in) |
| **RoleBinding** | Connects ServiceAccount to ClusterRole | You (create this manifest) |

**What you need to do:**
1. Find your ServiceAccount name and namespace
2. Choose Method 1 (direct SCC) or Method 2 (RoleBinding)
3. Create the manifest
4. Apply via ArgoCD or ask platform team to apply
5. Restart pods

The RoleBinding doesn't need a separate Role - it uses the built-in ClusterRole that OpenShift provides automatically!
