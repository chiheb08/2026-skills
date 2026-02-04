# Redis Enterprise — Argo CD and manifest examples

Example manifests to deploy **Redis Enterprise Cluster (REC)** and **Redis Enterprise Database (REDB)**.

## Option 1 — Single manifest file (REC + REDB in one YAML)

- **redis-enterprise-all-in-one.yaml** — REC and REDB in one file. Deploy with:

```bash
kubectl apply -f redis-enterprise-all-in-one.yaml
```

Use this when you prefer one file and no Helm/Argo CD, or when Argo CD syncs a directory (it will apply both resources).

## Option 2 — Separate manifests (REC + REDB + Argo CD Application)

- **rec.yaml** — RedisEnterpriseCluster (use kind `RedisEnterpriseCluster`, not "redisenterprise").
- **redb.yaml** — RedisEnterpriseDatabase; `spec.redisEnterpriseCluster.name` must match REC name.
- **application.yaml** — Argo CD Application; set `spec.source.repoURL` and `spec.source.path` to your repo.

**Deploy with Argo CD:** Push these files to your Git repo, then either create the app in Argo CD UI (point source to this path) or run:

```bash
kubectl apply -f application.yaml -n argocd
```

**Prerequisites:** Redis Enterprise operator installed (e.g. via Helm) in namespace `redis-enterprise`. REC and REDB must be created in the **same namespace** as the operator to avoid "cannot create resource in api group app.redislabs.com".

See [06-redis-enterprise-argocd-deployment.md](../06-redis-enterprise-argocd-deployment.md) for full steps and troubleshooting.
