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

## 5. Summary

| Topic | What to do |
|-------|------------|
| **"Cannot create resource" error** | Use **`RedisEnterpriseCluster`** or **`RedisEnterpriseDatabase`** (correct kind); ensure operator is installed; create REC/REDB in the **same namespace** as the operator (or fix RBAC/webhook). |
| **Deploy with Argo CD** | (1) Install operator (Helm) once. (2) Put REC and REDB YAML in Git. (3) Create Argo CD Application pointing at that repo/path. (4) Sync. |
| **Example files** | Use `redis-enterprise-argocd-example/rec.yaml`, `redb.yaml`, and `application.yaml`; set namespace and repo URL/path to your environment. |
| **Admission webhook "rec" not found** | Use sync waves (REC wave 0, REDB wave 1); ensure Argo CD destination namespace is `redis-enterprise` (same as operator); sync twice if REDB fails until REC is ready. See [Section 6](#6-troubleshooting-admission-webhook-rec-not-found). |
| **"Object has been modified" / "rec-0 not found" / "Waiting for first pod to bootstrap"** | Add Argo CD `ignoreDifferences` for REC `.status`; ensure REC namespace matches operator namespace; check StatefulSet/pods/PVC/events so `rec-0` can start. See [Section 6.1](#61-object-has-been-modified-and-pod-rec-0-not-found--waiting-for-first-pod-to-bootstrap). |

Using the correct resource names and the same namespace as the operator (with RBAC in place for Argo CD) resolves the “cannot create resource in api group app.redislabs.com” error and lets Argo CD deploy REC and REDB from Git.
