# Data Layer Resource Requirements (PostgreSQL & Redis)

Resource parameters and values for the data layer only, by expected user count. Use these under your Deployment/Pod `resources` and PVC `storage`; `max_connections` is a PostgreSQL server config setting.

Based on [infrastructure-sizing-700-1500-users.md](./infrastructure-sizing-700-1500-users.md).

---

## 700 users

### PostgreSQL

```yaml
resources:
  requests:
    cpu: "4"
    memory: "16Gi"
  limits:
    cpu: "4"
    memory: "16Gi"
# PVC / storage
storage: 50Gi
# PostgreSQL server config (not pod resources)
max_connections: 150
```

### Redis

```yaml
resources:
  requests:
    cpu: "4"
    memory: "16Gi"
  limits:
    cpu: "4"
    memory: "16Gi"
# PVC / storage (if persistent)
storage: 20Gi
```

---

## 1000 users

### PostgreSQL

```yaml
resources:
  requests:
    cpu: "8"
    memory: "32Gi"
  limits:
    cpu: "8"
    memory: "32Gi"
storage: 100Gi
max_connections: 250
```

### Redis

```yaml
resources:
  requests:
    cpu: "8"
    memory: "32Gi"
  limits:
    cpu: "8"
    memory: "32Gi"
storage: 32Gi
```

---

## 1500 users

### PostgreSQL

```yaml
resources:
  requests:
    cpu: "8"
    memory: "32Gi"
  limits:
    cpu: "8"
    memory: "32Gi"
storage: 100Gi
max_connections: 300
```

### Redis

```yaml
resources:
  requests:
    cpu: "8"
    memory: "32Gi"
  limits:
    cpu: "8"
    memory: "32Gi"
storage: 32Gi
```

---

## Quick reference table

| Users | Component  | CPU (request/limit) | Memory (request/limit) | Storage | max_connections (PG only) |
|-------|------------|----------------------|------------------------|---------|---------------------------|
| 700   | PostgreSQL | 4                    | 16Gi                   | 50Gi    | 150                       |
| 700   | Redis      | 4                    | 16Gi                   | 20Gi    | —                         |
| 1000  | PostgreSQL | 8                    | 32Gi                   | 100Gi   | 250                       |
| 1000  | Redis      | 8                    | 32Gi                   | 32Gi    | —                         |
| 1500  | PostgreSQL | 8                    | 32Gi                   | 100Gi   | 300                       |
| 1500  | Redis      | 8                    | 32Gi                   | 32Gi    | —                         |

---

**Usage:** Copy the `resources` block into your container spec; set `storage` on the PVC; set `max_connections` in PostgreSQL configuration (not in the pod resources).
