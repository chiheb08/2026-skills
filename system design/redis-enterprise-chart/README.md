# redis-enterprise Helm chart

Helm chart that deploys **Redis Enterprise Cluster (REC)** and **Redis Enterprise Database (REDB)** custom resources. The Redis Enterprise operator (installed separately via its own Helm chart or OLM) watches these and creates the actual cluster and database.

## Prerequisites

- Redis Enterprise operator installed in the target namespace (e.g. `redis-enterprise`).
- REC and REDB must be created in the **same namespace** as the operator.

## Install

```bash
# Install with default values (namespace redis-enterprise, rec my-rec, redb my-redb)
helm install redis-enterprise ./redis-enterprise-chart -n redis-enterprise

# Override namespace and/or values
helm install redis-enterprise ./redis-enterprise-chart -n redis-enterprise -f my-values.yaml
```

## Argo CD / GitOps

Use this chart as a Helm source in Argo CD:

- **Repository:** your Git repo URL.
- **Path:** path to this chart (e.g. `system design/redis-enterprise-chart`).
- **Helm:** enable Helm and optionally pass `values` or `valuesFile` in the Application spec.

## Values

See `values.yaml` for all options. Key ones:

- `namespace` — must match operator namespace.
- `rec.name`, `rec.nodes`, `rec.persistentSpec`, `rec.redisEnterpriseNodeResources`
- `redb.enabled`, `redb.name`, `redb.redisEnterpriseClusterName` (must equal `rec.name`), `redb.memorySize`, `redb.shardCount`, `redb.replication`
