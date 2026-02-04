# Redis Enterprise — Fix "Cannot Create Resource" and Deploy with Argo CD

You got an error like: **cannot create resource "redisenterprise" in API group "app.redislabs.com" in the namespace "..."**. This guide explains why that happens, how to fix it, and how to deploy Redis Enterprise (REC and REDB) using **Argo CD** with a Git repo (and Helm for the operator if needed).

---

## Table of Contents

1. [Why You Get "Cannot Create Resource" in app.redislabs.com](#1-why-you-get-cannot-create-resource-in-appredislabscom)
2. [Prerequisites Before Using Argo CD](#2-prerequisites-before-using-argocd)
3. [Steps to Deploy Redis Enterprise with Argo CD](#3-steps-to-deploy-redis-enterprise-with-argocd)
4. [Example Files and Git Repo Layout](#4-example-files-and-git-repo-layout)
5. [Summary](#5-summary)

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

### Folder structure

```
redis-enterprise-argocd-example/
  rec.yaml          # RedisEnterpriseCluster
  redb.yaml         # RedisEnterpriseDatabase (depends on REC)
  application.yaml  # Argo CD Application (optional)
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

## 5. Summary

| Topic | What to do |
|-------|------------|
| **"Cannot create resource" error** | Use **`RedisEnterpriseCluster`** or **`RedisEnterpriseDatabase`** (correct kind); ensure operator is installed; create REC/REDB in the **same namespace** as the operator (or fix RBAC/webhook). |
| **Deploy with Argo CD** | (1) Install operator (Helm) once. (2) Put REC and REDB YAML in Git. (3) Create Argo CD Application pointing at that repo/path. (4) Sync. |
| **Example files** | Use `redis-enterprise-argocd-example/rec.yaml`, `redb.yaml`, and `application.yaml`; set namespace and repo URL/path to your environment. |

Using the correct resource names and the same namespace as the operator (with RBAC in place for Argo CD) resolves the “cannot create resource in api group app.redislabs.com” error and lets Argo CD deploy REC and REDB from Git.
