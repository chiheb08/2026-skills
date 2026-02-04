# Redis Enterprise — Fix "Cannot Create Resource" and Deploy with Argo CD

You got an error like: **cannot create resource "redisenterprise" in API group "app.redislabs.com" in the namespace "..."**. This guide explains why that happens, how to fix it, and how to deploy Redis Enterprise (REC and REDB) using **Argo CD** with a Git repo (and Helm for the operator if needed).

---

## Table of Contents

1. [Why You Get "Cannot Create Resource" in app.redislabs.com](#1-why-you-get-cannot-create-resource-in-appredislabscom)
2. [Prerequisites Before Using Argo CD](#2-prerequisites-before-using-argocd)
3. [Steps to Deploy Redis Enterprise with Argo CD](#3-steps-to-deploy-redis-enterprise-with-argocd)
4. [Example Files and Git Repo Layout](#4-example-files-and-git-repo-layout)
5. [Summary](#5-summary)
6. [Troubleshooting: Admission Webhook "rec" Not Found](#6-troubleshooting-admission-webhook-rec-not-found)

---

## 1. Why You Get "Cannot Create Resource" in app.redislabs.com

The error means the cluster (or the namespace) does not allow creating that resource. Common causes:

| Cause | What to check | Fix |
|-------|----------------|-----|
| **Wrong resource name** | You may have used a name like `redisenterprise` or `RedisEnterprise`. | The correct **kinds** are **`RedisEnterpriseCluster`** (REC) and **`RedisEnterpriseDatabase`** (REDB). Use one of these in your YAML (`kind: RedisEnterpriseCluster` or `kind: RedisEnterpriseDatabase`). |
| **Operator not installed** | CRDs for `app.redislabs.com` are missing. | Install the Redis Enterprise operator (Helm or OperatorHub) so the CRDs and operator are present. |
| **Operator in another namespace** | The operator is often installed in one namespace (e.g. `redis-enterprise`) and may only watch that namespace. | Create REC and REDB **in the same namespace** where the operator is installed, **or** ensure the operator is configured to watch the namespace where you create them (e.g. cluster-wide or via label). |
| **RBAC** | Your user or service account does not have permission to create resources in API group `app.redislabs.com`. | Grant RBAC: create a Role (or ClusterRole) with `apiGroups: ["app.redislabs.com"]`, resources `redisenterpriseclusters`, `redisenterprisedatabases`, verbs `create`, `get`, `list`, `watch`, `update`, `patch`, `delete`, and bind it to your user or Argo CD’s service account in the target namespace. |
| **Admission webhook** | The operator’s admission webhook may reject the request or only apply to certain namespaces. | If you use `admission.limitToNamespace: true`, the webhook only applies to the operator’s namespace; create REC/REDB there, or relax the webhook configuration. |

**Quick checks:**

```bash
# 1) Correct resource names (CRDs exist)
kubectl get crd | grep redislabs
# You should see: redisenterpriseclusters.app.redislabs.com, redisenterprisedatabases.app.redislabs.com

# 2) Operator is running (replace NAMESPACE with operator namespace)
kubectl get deployment -n NAMESPACE redis-enterprise-operator

# 3) Try creating REC in the SAME namespace as the operator first
kubectl apply -f rec.yaml -n NAMESPACE
```

Use **`RedisEnterpriseCluster`** and **`RedisEnterpriseDatabase`** (exact spelling and capitalization) in your YAML.

---

## 2. Prerequisites Before Using Argo CD

1. **Redis Enterprise operator** is installed (e.g. via Helm in a dedicated namespace like `redis-enterprise`) and running.
2. **Decision:** Will REC/REDB live in the **same** namespace as the operator or a **different** one?
   - **Same namespace:** Easiest; no extra RBAC or webhook config.
   - **Different namespace:** Ensure the operator watches that namespace (or install operator there), and that RBAC allows Argo CD to create resources in `app.redislabs.com` in that namespace.
3. **Argo CD** is installed and has access to your Git repo.
4. **Git repo** where you will store REC and REDB manifests (and optionally the Argo CD Application manifest).

---

## 3. Steps to Deploy Redis Enterprise with Argo CD

You use **Helm** for the operator (as you already do); REC and REDB are typically **plain YAML** in Git that Argo CD syncs (no Helm chart for REC/REDB unless you have a custom one). The flow is:

1. **Install the operator once** (Helm or OperatorHub) — e.g. from a separate Argo CD app or manually.
2. **Put REC and REDB YAML in a Git repo** (e.g. your “deploy” or “gitops” repo).
3. **Register an Argo CD Application** that points at that repo and path; Argo CD syncs REC and REDB.

### Step 1 — Install the Redis Enterprise operator (if not already)

Install the operator in the namespace where you want it (e.g. `redis-enterprise`). Use Helm (as in [05-redis-enterprise-operator-deploy-and-variables.md](05-redis-enterprise-operator-deploy-and-variables.md)):

```bash
helm repo add redis https://helm.redis.io
helm repo update
helm install redis-enterprise-operator redis/redis-enterprise-operator \
  --version 7.8.6-8 \
  --namespace redis-enterprise \
  --create-namespace \
  --set openshift.mode=true
```

Or deploy the operator via a separate Argo CD Application (Helm source) if you prefer. REC/REDB will be created in the same namespace as the operator in this example.

### Step 2 — Create a Git repo layout for REC and REDB

In your Git repo (the one Argo CD syncs), create a folder for Redis Enterprise, for example:

```
your-gitops-repo/
  redis-enterprise/
    rec.yaml
    redb.yaml
    application.yaml   # optional: Argo CD Application manifest
```

Use the **same namespace** as the operator (e.g. `redis-enterprise`) in the manifests so you avoid “cannot create resource” due to namespace/webhook.

### Step 3 — Add REC and REDB manifests

- **rec.yaml:** One `RedisEnterpriseCluster` (see [Section 4](#4-example-files-and-git-repo-layout) or the example in `redis-enterprise-argocd-example/`).
- **redb.yaml:** One or more `RedisEnterpriseDatabase` with `spec.redisEnterpriseCluster.name` set to the REC name.

Ensure `metadata.namespace` in both matches the namespace where the operator runs (e.g. `redis-enterprise`).

### Step 4 — Create the Argo CD Application

**Option A — Argo CD UI**

1. Open Argo CD → **New App**.
2. **Application name:** e.g. `redis-enterprise`.
3. **Project:** default (or your project).
4. **Sync policy:** Manual or Auto (as you prefer).
5. **Source:**
   - **Repository URL:** your Git repo URL.
   - **Revision:** branch or tag (e.g. `main`).
   - **Path:** path to the folder that contains `rec.yaml` and `redb.yaml` (e.g. `redis-enterprise` or `system design/redis-enterprise-argocd-example`).
6. **Destination:**
   - **Cluster:** in-cluster (or your cluster URL).
   - **Namespace:** same as in your manifests (e.g. `redis-enterprise`).
7. Create the app; then **Sync** (and optionally enable **Prune** if you want Argo CD to remove resources when you delete them from Git).

**Option B — Argo CD Application manifest in Git**

Commit an `application.yaml` like the one in `redis-enterprise-argocd-example/application.yaml` (see Section 4). Point `spec.source.repoURL` and `spec.source.path` to your repo and path. Apply it once (or use an App of Apps):

```bash
kubectl apply -f application.yaml -n argocd
```

Then Argo CD will sync the Application and apply REC and REDB from Git.

### Step 5 — Sync and verify

- In Argo CD, open the `redis-enterprise` app and click **Sync** (if manual).
- Wait until REC is ready (operator creates StatefulSet, etc.); then REDB will become ready and the operator will create the database Service.
- Check resources:

```bash
kubectl get rec,redb -n redis-enterprise
kubectl get svc -n redis-enterprise
```

Your apps connect to the REDB’s Service (e.g. `my-redb:6379`).

---

## 4. Example Files and Git Repo Layout

Example files are in **`redis-enterprise-argocd-example/`** in this repo. Use them as a template; replace namespace, names, and repo URL with your values.

### Option: single manifest file (REC + REDB in one YAML)

You can deploy REC and REDB from **one file** instead of separate rec.yaml and redb.yaml:

- **redis-enterprise-all-in-one.yaml** — contains both `RedisEnterpriseCluster` and `RedisEnterpriseDatabase` (separated by `---`). Deploy with:

  ```bash
  kubectl apply -f redis-enterprise-all-in-one.yaml
  ```

Use this when you prefer a single manifest (no Helm) or when Argo CD syncs a directory that includes this file (Argo CD will apply both resources).

### Folder structure

```
redis-enterprise-argocd-example/
  redis-enterprise-all-in-one.yaml   # REC + REDB in one file (manifest option)
  rec.yaml                           # RedisEnterpriseCluster
  redb.yaml                          # RedisEnterpriseDatabase (depends on REC)
  application.yaml                   # Argo CD Application (optional)
```

### rec.yaml

- **kind:** `RedisEnterpriseCluster` (not “redisenterprise”).
- **metadata.namespace:** must match the namespace where the operator runs (e.g. `redis-enterprise`).
- Adjust `spec.nodes`, `persistentSpec`, `redisEnterpriseNodeResources`, and license/credentials as in [05-redis-enterprise-operator-deploy-and-variables.md](05-redis-enterprise-operator-deploy-and-variables.md).

### redb.yaml

- **kind:** `RedisEnterpriseDatabase`.
- **spec.redisEnterpriseCluster.name:** must match the REC `metadata.name` (e.g. `my-rec`).
- **metadata.namespace:** same as REC.

### application.yaml

- **spec.source.repoURL:** your Git repo URL (e.g. `https://github.com/your-org/your-repo.git`).
- **spec.source.path:** path to the directory that contains `rec.yaml` and `redb.yaml` (e.g. `redis-enterprise-argocd-example` or `system design/redis-enterprise-argocd-example`).
- **spec.destination.namespace:** same namespace as in rec.yaml/redb.yaml (e.g. `redis-enterprise`).

After pushing these files to Git, create the Application in Argo CD (UI or `kubectl apply -f application.yaml` in `argocd` namespace) and sync.

---

## 6. Troubleshooting: Admission Webhook "rec" Not Found

**Error:** Sync fails with:

```text
admission webhook "redisenterprise.admission.redislabs" denied the request: failed to get RedisEnterpriseCluster client: custom resource (RedisEnterpriseCluster) not found: redisenterpriseclusters.app.redislabs.com "rec" not found
```

**Cause:** The admission webhook validates the **REDB** (RedisEnterpriseDatabase) by looking up the **REC** (RedisEnterpriseCluster) it references (`spec.redisEnterpriseCluster.name`). If the REC does not exist yet (or is in a different namespace), the webhook denies the request.

**Fixes:**

| Fix | What to do |
|-----|------------|
| **1. Apply REC before REDB (sync order)** | Argo CD may apply resources in an order where REDB is created before REC. Use **sync waves** so REC is applied first, then REDB: add `argocd.argoproj.io/sync-wave: "0"` to the REC metadata and `argocd.argoproj.io/sync-wave: "1"` to the REDB metadata. The example files `redis-enterprise-all-in-one.yaml` and `redb.yaml` include these annotations. |
| **2. Same namespace** | REC and REDB must be in the **same namespace** as each other and as the Redis Enterprise operator. In Argo CD, set **Destination → Namespace** to that namespace (e.g. `redis-enterprise`). If your Application syncs to a different namespace (e.g. `bai32-baipi-gat...`), the REC may be created there but the operator (and webhook) may be looking in `redis-enterprise` — or the REC name may not match. Use **one** namespace for operator, REC, and REDB. |
| **3. Sync twice** | After adding sync waves, sync the Application. If REDB still fails (e.g. REC is not “ready” yet), wait for the REC to become ready (`kubectl get rec -n redis-enterprise`), then sync again so REDB is created after the REC exists and is admitted. |
| **4. Check REC name** | The REDB’s `spec.redisEnterpriseCluster.name` must match the REC’s `metadata.name` exactly (e.g. `rec` or `my-rec`). If your REC is named `my-rec`, the REDB must reference `my-rec`, not `rec`. |

**Quick check:**

```bash
# REC must exist in the same namespace as REDB
kubectl get rec -n redis-enterprise
# Ensure the name matches what the REDB references (e.g. rec or my-rec)
```

---

### 6.1 "Object has been modified" and "Pod rec-0 not found" / "Waiting for first pod to bootstrap"

**Errors you may see in the redis-enterprise-operator logs:**

1. `Operation cannot be fulfilled on redisenterpriseclusters.app.redislabs.com "rec": the object has been modified; please apply your changes first`
2. `could not get stateful set pod: Pod "rec-0" not found`
3. `Failed updating defaults for REC spec`
4. `Error while validating first pod bootstrapping completion` / `Waiting for first pod to bootstrap`

**Causes and fixes:**

| Error | Cause | Fix |
|-------|--------|-----|
| **Object has been modified** | Argo CD (or GitOps) keeps reapplying the REC from Git. The **operator** also updates the REC (status, defaults, or spec). The two updates conflict: Git says "apply this spec," the server has a newer version → conflict. | **Option A:** Tell Argo CD to **ignore** operator-driven changes on the REC. In the Argo CD Application spec add `ignoreDifferences` (or in the app UI: App Details → Diffing Customization). Example so Argo CD ignores REC `status` and avoids overwriting operator mutations: add a difference with `group: app.redislabs.com`, `kind: RedisEnterpriseCluster`, `jqPathExpressions: [.status]`. If the operator also mutates parts of `spec`, add `.spec` to the list or ignore the whole REC except `metadata` (use with care). **Option B:** Use **Server-Side Apply** for the REC. **Option C:** After the REC is created once, stop managing the REC via GitOps; only manage REDB and other resources. |
| **Pod rec-0 not found** | The operator created a StatefulSet for the REC but the first pod (`rec-0`) doesn’t exist or isn’t ready yet. Common causes: PVC pending, image pull failure, resource quotas, node selector/taints, or the REC is in a namespace the operator doesn’t fully manage. | Check: `kubectl get sts,pods,pvc -n <rec-namespace>` (use the namespace where the REC lives, e.g. `bai32-baipi-gateway-...`). Ensure the StatefulSet exists and that pods are being created. Check `kubectl describe pod rec-0 -n <rec-namespace>` and `kubectl get events -n <rec-namespace>` for image pull, PVC, or scheduling errors. Fix PVC storage class, image pull secrets, or resource requests so the pod can start. |
| **Failed updating defaults for REC spec** | The operator tries to set default values on the REC but the update fails — often because of the **object has been modified** conflict above (Argo CD reapplied the REC at the same time). | Resolve the conflict first (ignore differences or server-side apply). Then let the operator reconcile; avoid syncing the REC from Git repeatedly until the operator has stabilized the REC. |
| **Waiting for first pod to bootstrap** | The operator is waiting for `rec-0` to finish bootstrapping. If `rec-0` never appears or never becomes ready, the operator stays in this loop. | Same as **Pod rec-0 not found**: ensure the REC’s StatefulSet and first pod can be created and run (PVC, image, resources, namespace). If the REC is in a namespace like `bai32-baipi-gateway-dev` while the operator is in `redis-enterprise`, confirm the operator is installed to watch that namespace (or move REC/REDB to `redis-enterprise`). |

**Argo CD ignore differences (for "object has been modified"):** Add this to your Application so Argo CD does not overwrite the REC’s status (and thus reduce conflicts with the operator):

```yaml
spec:
  ignoreDifferences:
    - group: app.redislabs.com
      kind: RedisEnterpriseCluster
      jqPathExpressions:
        - .status
```

If the operator also mutates `spec` (e.g. defaults), you can add `.spec` to `jqPathExpressions` — test so you don’t ignore fields you intend to manage from Git.

**Namespace check:** Your logs show the REC in namespace `bai32-baipi-gateway-baipi-gateway-dev...`. The Redis Enterprise operator is usually installed in a single namespace (e.g. `redis-enterprise`). If the operator is in `redis-enterprise` and the REC is in `bai32-baipi-gateway-...`, either (1) install the operator in that namespace too, or (2) move REC and REDB to the operator’s namespace (`redis-enterprise`) and point your Argo CD app’s **Destination → Namespace** to `redis-enterprise`. That avoids confusion and ensures the operator manages the REC and creates the StatefulSet/pods there.

**Quick checks:**

```bash
# Replace NAMESPACE with your REC namespace (e.g. bai32-baipi-gateway-dev or redis-enterprise)
kubectl get rec,sts,pods,pvc -n NAMESPACE
kubectl describe rec rec -n NAMESPACE
kubectl get events -n NAMESPACE --sort-by='.lastTimestamp'
```

---

### 6.2 Operator and REC in the same namespace — what to do next

If the **operator and REC are already in the same namespace** but you still see "object has been modified", "rec-0 not found", or "Waiting for first pod to bootstrap", follow this checklist.

**Step 1 — Stop Argo CD from fighting the operator (object modified)**

1. Add **ignoreDifferences** to your Argo CD Application for the REC (see YAML above in 6.1). That stops Argo CD from overwriting the operator’s changes to the REC.
2. Optionally **turn off auto-sync** for the Redis Enterprise app temporarily (Argo CD → your app → App Details → disable "Auto-Sync"). You can sync once manually after fixing things, then turn auto-sync back on.

**Step 2 — See why `rec-0` isn’t starting (same namespace)**

Run these in the **namespace where both the operator and REC live** (replace `YOUR_NS` with that namespace, e.g. `redis-enterprise` or `bai32-baipi-gateway-baipi-gateway-dev`):

```bash
export NS=YOUR_NS

# 1) REC, StatefulSet, Pods, PVCs
kubectl get rec,sts,pods,pvc -n $NS

# 2) Events (image pull, scheduling, PVC, OOM)
kubectl get events -n $NS --sort-by='.lastTimestamp' | tail -50

# 3) If rec-0 exists but isn’t ready
kubectl describe pod rec-0 -n $NS

# 4) If the StatefulSet exists but no pods
kubectl describe sts rec -n $NS
```

**What to look for:**

| Symptom | Likely cause | Fix |
|--------|---------------|-----|
| No StatefulSet `rec` | Operator didn’t create it (conflict or REC not admitted). | Ensure ignoreDifferences is set; sync once and check operator logs. |
| StatefulSet exists, no pods | Pods not scheduled or not created. | Check `kubectl get events` for FailedScheduling, and `kubectl describe sts rec` for template/volumes. |
| PVC stuck in Pending | Storage class missing or quota. | Create/default StorageClass, or set `persistentSpec.storageClassName` in the REC to an existing class; check quotas. |
| ImagePullBackOff | Image not found or pull secret missing. | REC uses Red Hat registry (`registry.connect.redhat.com/redislabs/...`). Create an image pull secret for Red Hat (or your registry) and add `spec.pullSecrets` to the REC. |
| CrashLoopBackOff / OOMKilled | Not enough memory or CPU. | Increase `redisEnterpriseNodeResources` in the REC (e.g. requests/limits memory ≥ 4Gi, cpu ≥ 2). |
| OpenShift: pod blocked by security | Security context / SCC. | Grant the Redis Enterprise SCC to the REC’s service account, or use the operator’s recommended SCC (see Redis Enterprise OpenShift docs). |

**Step 3 — OpenShift: Red Hat images and pull secret**

If you use the Red Hat registry (`registry.connect.redhat.com/redislabs/...`), ensure the namespace has a pull secret so the REC pods can pull images:

```bash
# Create pull secret (replace with your Red Hat registry credentials)
kubectl create secret docker-registry redhat-pull-secret \
  --docker-server=registry.connect.redhat.com \
  --docker-username=YOUR_REDHAT_USER \
  --docker-password=YOUR_REDHAT_PASSWORD \
  -n $NS

# Add to default service account (or the REC’s service account)
kubectl patch serviceaccount default -n $NS -p '{"imagePullSecrets":[{"name":"redhat-pull-secret"}]}'
```

If the REC uses a dedicated service account, add the same `imagePullSecrets` to that account, or set `spec.pullSecrets` in the REC to `[{ "name": "redhat-pull-secret" }]`.

**Step 4 — One-time: let the operator settle**

1. Pause or disable auto-sync for the Redis Enterprise app.
2. Apply the REC once from Git (or leave it as-is if it already exists).
3. Add ignoreDifferences for the REC (status, and spec if the operator mutates it).
4. Wait for the operator to create the StatefulSet and for `rec-0` to become Ready (fix PVC/image/resources from Step 2 if needed).
5. Re-enable auto-sync or sync manually; then create the REDB (sync wave 1) if you use it.

**Quick recap (same namespace):**

1. Add **ignoreDifferences** for REC `.status` (and optionally `.spec`) on the Application.  
2. Run the **kubectl** commands above in the shared namespace and fix PVC / image pull / resources / SCC.  
3. Optionally **disable auto-sync** until REC is healthy, then sync again.

---

## 5. Summary

| Topic | What to do |
|-------|------------|
| **"Cannot create resource" error** | Use **`RedisEnterpriseCluster`** or **`RedisEnterpriseDatabase`** (correct kind); ensure operator is installed; create REC/REDB in the **same namespace** as the operator (or fix RBAC/webhook). |
| **Deploy with Argo CD** | (1) Install operator (Helm) once. (2) Put REC and REDB YAML in Git. (3) Create Argo CD Application pointing at that repo/path. (4) Sync. |
| **Example files** | Use `redis-enterprise-argocd-example/rec.yaml`, `redb.yaml`, and `application.yaml`; set namespace and repo URL/path to your environment. |
| **Admission webhook "rec" not found** | Use sync waves (REC wave 0, REDB wave 1); ensure Argo CD destination namespace is `redis-enterprise` (same as operator); sync twice if REDB fails until REC is ready. See [Section 6](#6-troubleshooting-admission-webhook-rec-not-found). |
| **"Object has been modified" / "rec-0 not found" / "Waiting for first pod to bootstrap"** | Add Argo CD `ignoreDifferences` for REC `.status`; ensure REC namespace matches operator namespace; check StatefulSet/pods/PVC/events so `rec-0` can start. See [Section 6.1](#61-object-has-been-modified-and-pod-rec-0-not-found--waiting-for-first-pod-to-bootstrap). |
| **Operator and REC in same namespace but still failing** | Follow [Section 6.2](#62-operator-and-rec-in-the-same-namespace--what-to-do-next): add ignoreDifferences, disable auto-sync temporarily, run the kubectl checklist (REC/STS/pods/PVC/events), fix PVC/image pull/resources/SCC, then re-sync. |

Using the correct resource names and the same namespace as the operator (with RBAC in place for Argo CD) resolves the “cannot create resource in api group app.redislabs.com” error and lets Argo CD deploy REC and REDB from Git.
