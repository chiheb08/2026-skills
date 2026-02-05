# Redis Enterprise — How to Deploy and Mitigate Known Issues

This page is based on the Redis Enterprise deployment doc (prerequisites, recommendations, known issues). It tells you **how to deploy** the REC and **how to avoid or fix** the issues that often cause REC to get stuck (Progressing, REDB not created).

---

## 1. Prerequisites (from the doc)

Before deploying a Redis Enterprise Cluster (REC), ensure:

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Nodes** | 3 | 3 |
| **RAM per node** | 3 GB | 4 GB |
| **Persistent storage per node** | 10 GB free | 20 GB |
| **Kubernetes** | 1.9+ | — |

Your REC YAML should ask for at least 4Gi memory and 20Gi storage per node (we already use that in the example manifests).

---

## 2. How to Deploy the REC (step by step)

**Step 1 — Install the Redis Enterprise operator**

The operator must be installed first (e.g. from OperatorHub or Helm) in the namespace where you want the REC. Your screenshot shows the operator in namespace `bai32-baipi-gateway-baipi-gateway-dev-01` with status **Succeeded**. So the operator is already there.

**Step 2 — Use the same namespace as the operator**

Create the REC (and later the REDB) in the **same** namespace as the operator. In your case that is `bai32-baipi-gateway-baipi-gateway-dev-01` (or whatever namespace shows in the operator’s ClusterServiceVersion). Set this in your REC YAML:

```yaml
metadata:
  name: rec
  namespace: bai32-baipi-gateway-baipi-gateway-dev-01   # same as operator
```

And in Argo CD set **Destination → Namespace** to that same namespace.

**Step 3 — Deploy the REC manifest**

Use a REC YAML that has at least:

- **nodes:** 3  
- **persistentSpec.enabled:** true  
- **persistentSpec.volumeSize:** 20Gi (or 10Gi minimum)  
- **redisEnterpriseNodeResources:** at least 4Gi memory, 2 CPU per node (see doc)  
- **persistentSpec.storageClassName:** set explicitly if your cluster has **no default Storage Class** (see Mitigation 2 below)

Example (minimal):

```yaml
apiVersion: app.redislabs.com/v1
kind: RedisEnterpriseCluster
metadata:
  name: rec
  namespace: bai32-baipi-gateway-baipi-gateway-dev-01
spec:
  nodes: 3
  persistentSpec:
    enabled: true
    volumeSize: 20Gi
    # storageClassName: "your-storage-class"   # set this if there is no default (see Mitigation 2)
  redisEnterpriseNodeResources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "2"
      memory: "4Gi"
```

Apply with `kubectl apply -f rec.yaml` or via Argo CD (with sync waves: REC wave 0, REDB wave 1).

**Step 4 — Deploy the REDB only after the REC is ready**

Create the REDB (database) only after the REC exists and is ready. Use sync wave 1 for the REDB so Argo CD applies it after the REC. REDB YAML must have `spec.redisEnterpriseCluster.name` equal to the REC’s `metadata.name` (e.g. `rec`).

---

## 3. Mitigate the Known Issues (from the doc)

The doc lists two recommendations/known issues. Doing these **before** or **right after** deploying greatly reduces the chance of REC stuck in Progressing and REDB not being created.

---

### Mitigation 1: If you change the Redis Enterprise Cluster name (OpenShift)

**What “change the REC name” means:**  
The **REC name** is the `metadata.name` in your REC YAML (e.g. `rec` or `my-rec`). The doc says “if you change the cluster name from its default” — meaning: you set the REC name to something **you** chose (e.g. `rec`) instead of whatever the operator’s default or template suggests. In practice, you almost always set a name, so you often need this step.

**Why it matters on OpenShift:**  
On OpenShift, pods run under **Security Context Constraints (SCC)**. The Redis Enterprise operator creates a **service account** for your REC so the REC pods can run. That service account is usually named the **same as the REC** (e.g. REC name `rec` → service account `rec`). There is an SCC called `redis-enterprise-scc-v2` that the REC pods need. By default, that SCC might not be granted to **your** REC’s service account (especially when you use a custom REC name). So the REC pods can be **blocked by security** and never start — the REC stays Progressing.

**What to do:**  
Grant the SCC to the REC’s service account so the REC pods are allowed to run. After creating the REC (or before, if you already know the name), run this once per project/namespace. Replace `MY_PROJECT` with the **namespace** where the REC lives, and replace `REC_NAME` with the **name** of the Redis Enterprise Cluster (e.g. `rec`), which is usually also the service account name:

```bash
oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:MY_PROJECT:REC_NAME
```

Example if your REC is named `rec` in namespace `bai32-baipi-gateway-baipi-gateway-dev-01`:

```bash
oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:bai32-baipi-gateway-baipi-gateway-dev-01:rec
```

If the REC uses a different service account name, use that instead of `rec`. Check with:

```bash
kubectl get rec rec -n YOUR_NAMESPACE -o jsonpath='{.spec.serviceAccountName}'
```

If nothing is set, the operator often uses a service account with the same name as the REC (e.g. `rec`).

---

### Mitigation 2: Storage Class (avoid “installation could fail”)

**Issue:** If you do **not** set `persistentSpec.storageClassName` in the REC, the cluster uses the **default** Storage Class. If the Kubernetes cluster has **no default Storage Class**, the doc says the installation of the cluster can **fail**. That often shows as PVCs stuck in **Pending** and REC pods never starting (REC stuck Progressing).

**What to do:**

1. **Check if there is a default Storage Class:**

   ```bash
   kubectl get storageclass
   ```

   Look for a line where one of the names has **(default)** next to it.

2. **If there is a default:**  
   You can leave `persistentSpec.storageClassName` unset in the REC, and the REC will use it.

3. **If there is no default:**  
   You **must** set `persistentSpec.storageClassName` in the REC to an existing Storage Class name. For example, if you have a class named `gp3` or `standard`:

   ```yaml
   spec:
     persistentSpec:
       enabled: true
       volumeSize: 20Gi
       storageClassName: "gp3"    # use your cluster’s Storage Class name
   ```

   Then apply or sync the REC again. The PVCs should provision and the REC pods can start.

**Summary:** No default Storage Class + no `storageClassName` in REC → installation can fail (PVC Pending, REC stuck Progressing). Always set `storageClassName` if there is no default.

---

## 4. How this fixes the issues you had

| Problem you had | How deploy + mitigations help |
|-----------------|--------------------------------|
| **REC stuck in Progressing** | Often caused by PVC Pending (no default Storage Class). **Mitigation 2** (check Storage Class, set `storageClassName` if no default) fixes that. **Mitigation 1** (SCC for REC name) avoids pods being blocked by security on OpenShift. |
| **REDB never created** | REDB is created only after the REC is ready. Fixing REC (Storage Class, SCC, ignoreDifferences, operator not fighting Argo CD) lets the REC become ready; then REDB (sync wave 1) can be created. See [07-redis-enterprise-problems-fix-simple.md](07-redis-enterprise-problems-fix-simple.md). |
| **Errors in REC pod / operator** | Same root causes: PVC, permissions (SCC), or Argo CD vs operator conflict. Follow the mitigations above and the steps in the simple guide (ignoreDifferences, disable auto-sync, fix PVC/image/memory). |

---

## 5. Checklist (deploy + mitigate)

1. **Operator installed** in a namespace (e.g. `bai32-baipi-gateway-baipi-gateway-dev-01`).  
2. **REC and REDB** in the **same** namespace as the operator.  
3. **REC YAML:** nodes 3, persistentSpec enabled, volumeSize 20Gi, memory ≥ 4Gi per node.  
4. **Storage Class:** run `kubectl get storageclass`. If no **(default)**, set `persistentSpec.storageClassName` in the REC to an existing class.  
5. **OpenShift / custom REC name:** run `oc adm policy add-scc-to-user redis-enterprise-scc-v2 system:serviceaccount:NAMESPACE:REC_NAME`.  
6. **Argo CD:** add ignoreDifferences for REC `.status`; use sync waves (REC 0, REDB 1); disable auto-sync until REC is healthy if needed.  
7. **Deploy REC** (kubectl or Argo CD). Wait for REC to be ready (pods Running).  
8. **Deploy REDB** (after REC is ready; wave 1 if using Argo CD).

Doing steps 4 and 5 before or right after deploying the REC mitigates the two known issues from the doc and reduces the chance of REC stuck in Progressing and REDB not being created.
