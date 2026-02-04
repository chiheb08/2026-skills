# Redis Enterprise — Argo CD example

Example manifests to deploy **Redis Enterprise Cluster (REC)** and **Redis Enterprise Database (REDB)** via Argo CD.

- **rec.yaml** — RedisEnterpriseCluster (use kind `RedisEnterpriseCluster`, not "redisenterprise").
- **redb.yaml** — RedisEnterpriseDatabase; `spec.redisEnterpriseCluster.name` must match REC name.
- **application.yaml** — Argo CD Application; set `spec.source.repoURL` and `spec.source.path` to your repo.

**Prerequisites:** Redis Enterprise operator installed (e.g. via Helm) in namespace `redis-enterprise`. REC and REDB must be created in the **same namespace** as the operator to avoid "cannot create resource in api group app.redislabs.com".

**Deploy:** Push these files to your Git repo, then either create the app in Argo CD UI (point source to this path) or run:

```bash
kubectl apply -f application.yaml -n argocd
```

See [06-redis-enterprise-argocd-deployment.md](../06-redis-enterprise-argocd-deployment.md) for full steps and troubleshooting.
