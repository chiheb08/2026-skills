# Redis Enterprise — Deep Dive: Fix "ConfigMap rec-bulletin-board not found"

This document explains **why** the Redis Enterprise operator logs "Failed to retrieve bulletin board" or "Failed to update bulletin board: ConfigMap rec-bulletin-board not found", and **how to fix it** step by step.

---

## 1. What is the rec-bulletin-board ConfigMap?

- The Redis Enterprise operator uses a **ConfigMap** named **`<rec-name>-bulletin-board`** (e.g. `rec-bulletin-board` when your REC is named `rec`). It is an **internal** coordination object: the operator uses it during REC bootstrap and reconciliation to track cluster state and coordinate the first pod and subsequent nodes.
- The **operator** is supposed to **create** this ConfigMap when it sets up the REC. It is not something you create yourself; it is created by the operator as part of its reconciliation loop.
- Redis’s public docs do not describe this ConfigMap in detail; it is part of the operator’s internal design. The operator architecture doc states that the operator “creates supporting Kubernetes resources including StatefulSets and ConfigMaps as needed” during reconciliation.

So: **rec-bulletin-board** = internal operator ConfigMap for REC bootstrap/coordination. The operator creates it. If it is missing, the operator keeps trying to read or update it and logs “not found”.

---

## 2. Why does the ConfigMap go missing or never get created?

From how Kubernetes and the operator behave, the ConfigMap can be missing for these reasons:

| Cause | What happens |
|------|-------------------------------|
| **1. Conflict with Argo CD ("object has been modified")** | The operator runs a **reconciliation loop**: it reads the REC, updates the REC (e.g. status or defaults), then creates or updates resources (StatefulSet, ConfigMaps, etc.). If **Argo CD** reapplies the REC from Git at the same time, the API server can reject the operator’s update with “the object has been modified; please apply your changes first.” When that happens, the operator’s step fails. The operator may not reach the step that creates `rec-bulletin-board`, or the next reconciliation cycle may try to **read** the bulletin board before **creating** it (race). So the ConfigMap never appears or is missing long enough that you see “not found” repeatedly. |
| **2. RBAC — operator cannot create ConfigMaps** | The operator runs under a **ServiceAccount** and needs a **Role** (or ClusterRole) that allows `create`, `update`, `get`, `list`, `watch`, `delete` on **ConfigMaps** in the **namespace where the REC lives**. If the operator is installed via Helm or OLM in that same namespace, the bundled Role usually includes ConfigMaps. If the operator manages another namespace (multi-namespace) or the Role was customized and omits ConfigMaps, the operator cannot create `rec-bulletin-board` and you get “not found”. |
| **3. ConfigMap was deleted** | The operator created the ConfigMap, but something **deleted** it later: e.g. Argo CD **prune** (if the ConfigMap is not in Git), a manual delete, or another controller. The operator then tries to read/update it and logs “not found”. |
| **4. Wrong namespace** | The operator is looking for `rec-bulletin-board` in the **same namespace as the REC**. If the REC was created in namespace A but the operator is reconciling from namespace B, or the operator’s Role only allows access in one namespace, the ConfigMap might be created in the wrong place or not at all. |

In practice, **cause 1 (conflict with Argo CD)** is the most common: the operator never gets a clean run to create the ConfigMap because GitOps keeps overwriting the REC.

---

## 3. Step-by-step fix (in order)

Do these in order. Replace `YOUR_NAMESPACE` with the namespace where your REC lives (and where the operator runs, if same namespace). Replace `rec` with your REC name if different.

---

### Step 1 — Stop the conflict with Argo CD (must do first)

1. Add **ignoreDifferences** for the REC on your Argo CD Application so Argo CD does not overwrite the REC’s `.status` (and optionally other operator-managed fields). Example:
   ```yaml
   spec:
     ignoreDifferences:
       - group: app.redislabs.com
         kind: RedisEnterpriseCluster
         jqPathExpressions:
           - .status
   ```
2. **Disable Auto-Sync** for the Redis Enterprise Application in Argo CD (App Details → uncheck Auto-Sync).
3. **Sync once** manually so the REC is applied from Git. Then **do not sync again** for at least 5–10 minutes so the operator can run without being overwritten.

This gives the operator a window to complete reconciliation and create the ConfigMap.

---

### Step 2 — Check if the ConfigMap exists and in which namespace

```bash
export NS=YOUR_NAMESPACE
kubectl get configmap rec-bulletin-board -n $NS
```

- If it **exists** → the operator may have created it after you fixed the conflict. Check operator logs again; the “not found” errors may stop. If they continue, the operator might be looking in another namespace (see Step 4).
- If it **does not exist** → the operator has not created it yet. Proceed to Step 3 and Step 4.

---

### Step 3 — Verify operator RBAC (can it create ConfigMaps?)

The operator’s ServiceAccount must have permission to create/update ConfigMaps in the **REC’s namespace**.

**A. Same namespace (operator and REC in one namespace)**

List the Role bound to the operator’s ServiceAccount in that namespace:

```bash
kubectl get rolebinding -n $NS -o wide | grep redis-enterprise
kubectl get role -n $NS -o yaml | grep -A 20 "name: redis-enterprise-operator"
```

Or get the Role and check for `configmaps`:

```bash
kubectl get role redis-enterprise-operator -n $NS -o yaml
```

Ensure there is a rule with `resources: ["configmaps"]` and verbs including `create`, `update`, `get`, `list`, `watch`, `patch`, `delete`. If not, add a rule like:

```yaml
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["create", "delete", "get", "list", "patch", "update", "watch"]
```

**B. Multi-namespace (operator in namespace A, REC in namespace B)**

The operator needs a **ClusterRole** (or a Role in namespace B) that allows ConfigMap create/update in namespace B, and a **RoleBinding** in namespace B binding that role to the operator’s ServiceAccount. Check the Redis Enterprise multi-namespace docs and ensure the operator has ConfigMap permissions in the REC’s namespace.

If RBAC was wrong, fix it, then wait for the next reconciliation (or restart the operator pod). The operator should then be able to create `rec-bulletin-board`.

---

### Step 4 — Confirm REC and operator namespace

Ensure the REC is in the **same namespace** that the operator is watching and where it has RBAC:

```bash
kubectl get rec -n $NS
kubectl get pods -n $NS -l app.kubernetes.io/name=redis-enterprise-operator
```

If the operator runs in a different namespace and is configured for multi-namespace, ensure the REC’s namespace is in the operator’s list of managed namespaces and that the operator has ConfigMap permissions there (Step 3).

---

### Step 5 — Let the operator run without sync

After fixing ignoreDifferences and disabling auto-sync:

1. Do **not** sync the Redis app again for 5–10 minutes.
2. Watch the operator create resources:
   ```bash
   watch "kubectl get rec,sts,pods,configmap -n $NS | grep -E 'rec|NAME'"
   ```
3. Check for `rec-bulletin-board`:
   ```bash
   kubectl get configmap -n $NS | grep rec
   ```
4. Check operator logs for other errors (RBAC, image pull, etc.):
   ```bash
   kubectl logs -n $NS deployment/redis-enterprise-operator -f --tail=100
   ```

If the conflict is gone and RBAC is correct, the operator should create `rec-bulletin-board` and the “not found” messages should stop.

---

### Step 6 — If Argo CD might be pruning the ConfigMap

If the ConfigMap appears and then disappears, Argo CD might be **pruning** it because it is not in your Git repo (the operator creates it in the cluster, not from Git). Options:

- **Option A:** In the Argo CD Application, turn off **Prune** (or use a prune allow-list so the operator-created ConfigMaps are not deleted). Then the operator can keep the ConfigMap.
- **Option B:** Do not manage the REC namespace with Argo CD prune enabled for resources the operator creates; or use a separate Application that only manages the REC/REDB YAML and does not prune operator-created resources.

---

### Step 7 — Last resort: delete the REC and re-apply (only if safe)

If there is **no important data** in this REC and you have already:

- added ignoreDifferences,
- disabled auto-sync,
- fixed RBAC so the operator can create ConfigMaps,

then you can delete the REC and let the operator recreate everything (including the bulletin board ConfigMap):

```bash
kubectl delete rec rec -n $NS
```

Then **sync once** from Argo CD (or apply your REC YAML again). Do **not** sync again for several minutes. The operator will reconcile the new REC and should create `rec-bulletin-board`, then the StatefulSet and pods. Only do this if you can afford to lose the current REC and its data.

---

## 4. Summary: root cause and fix order

| Root cause | Fix |
|------------|-----|
| **Argo CD vs operator conflict** | Add ignoreDifferences for REC `.status`; disable Auto-Sync; sync once and wait 5–10 minutes (Step 1, 5). |
| **Operator cannot create ConfigMaps (RBAC)** | Ensure the operator’s Role in the REC namespace includes `configmaps` with create/update/get/list/watch (Step 3). |
| **ConfigMap deleted (e.g. by prune)** | Disable prune or exclude operator-created resources from prune (Step 6). |
| **Wrong namespace** | Put REC and operator in the same namespace, or fix multi-namespace RBAC (Step 4). |
| **Still missing after all above** | Delete REC and re-apply once conflict and RBAC are fixed (Step 7, only if safe). |

The “rec-bulletin-board not found” log means the operator is trying to use an internal ConfigMap that it should have created but that is missing. Stopping the conflict with Argo CD and ensuring RBAC and namespace are correct usually allows the operator to create it. If not, use the last-resort delete and re-apply after fixing conflict and RBAC.
