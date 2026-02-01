# Data Layer Resource Requirements (PostgreSQL & Redis)

Resource parameters and values for the data layer only, by expected user count. Use these under your Deployment/Pod `resources` and PVC `storage`; `max_connections` is a PostgreSQL server config setting.

Based on [infrastructure-sizing-700-1500-users.md](./infrastructure-sizing-700-1500-users.md).

---

## Why these values? (Simple justification)

We size PostgreSQL and Redis from **how many users you have** and **how many requests per second** that creates. More users → more traffic → more connections and data → we give more CPU, RAM, and storage.

---

### 1. What we assume per user tier

| Users | Roughly… | LiteLLM pods | Workers total |
|-------|----------|--------------|----------------|
| 700   | ~20 requests/sec at peak | 3 pods × 4 workers | 12 workers |
| 1000  | ~30 requests/sec at peak | 5 pods × 4 workers | 20 workers |
| 1500  | ~50 requests/sec at peak | 6 pods × 4 workers | 24 workers |

**Two things that drive sizing:**

1. **Requests per second (RPS)** — more RPS → more spend logs, more Redis work → need more storage, CPU, and RAM.
2. **Number of workers** — each worker can open connections to PostgreSQL → more workers → need a higher `max_connections` and enough CPU/RAM for those connections.

---

### 2. Simple diagram: why we need more when users grow

```
  MORE USERS  -->  More requests/sec (RPS)
       |
       +------------------+------------------+
       v                  v                  v
  PostgreSQL          Redis             LiteLLM
  - More log rows     - More checks      - More workers
    -> more storage     -> more CPU        -> more connections
  - More connections  - More cache
    -> more CPU/RAM      -> more RAM
```

So: **700 users** = less traffic → we give **less**. **1000–1500 users** = more traffic → we give **more**.

---

### 3. PostgreSQL — why these numbers

**CPU:** At 700 users (~20 RPS, 12 workers), **4 vCPU** is enough. At 1000–1500 users (more RPS and workers), **8 vCPU** so the DB is not slow.

**Memory:** PostgreSQL caches data and uses RAM per connection. 150 connections → **16 Gi**. 250–300 connections → **32 Gi**.

**Storage**

- Spend logs grow (one row per request). Example: 20 req/sec × 30 days ≈ tens of Gi. **50 Gi** for 700; **100 Gi** for 1000–1500 (so you can keep 30+ days). **max_connections:** LiteLLM workers each open several connections. Set PostgreSQL **above** that total and leave some for admin.

- **700 users:** 3 pods × 4 workers × 10 = **120**; add 30 → **150**.
- **1000 users:** 5 × 4 × 10 = **200**; add 50 → **250**.
- **1500 users:** 6 × 4 × 10 = **240**; add 60 → **300**.

More detail: [litellm-data-layer-technical-challenges.md](./litellm-data-layer-technical-challenges.md).

---

### 4. Redis — why these numbers

**CPU:** ~20 RPS → **4 vCPU** is enough. ~30–50 RPS → **8 vCPU** so Redis stays fast.

**Memory:** Redis holds cache, rate-limit counters, and a queue of spend updates. **16 Gi** for 700; **32 Gi** when RPS doubles (1000–1500).

**Storage:** Only if you enable persistence (snapshots). **20 Gi** for 700; **32 Gi** for 1000–1500.

---

### 5. One picture per tier

**700 users:** [ 3 LiteLLM pods ] → PostgreSQL: 4 CPU, 16 Gi, 50 Gi disk, max_connections 150. Redis: 4 CPU, 16 Gi, 20 Gi disk.

**1000 users:** [ 5 LiteLLM pods ] → PostgreSQL: 8 CPU, 32 Gi, 100 Gi disk, max_connections 250. Redis: 8 CPU, 32 Gi, 32 Gi disk.

**1500 users:** [ 6 LiteLLM pods ] → PostgreSQL: 8 CPU, 32 Gi, 100 Gi disk, max_connections 300. Redis: 8 CPU, 32 Gi, 32 Gi disk.

---

### 6. Quick summary

| Users | PostgreSQL | Redis |
|-------|------------|--------|
| 700   | 4 CPU, 16 Gi, 50 Gi, 150 conn | 4 CPU, 16 Gi, 20 Gi |
| 1000  | 8 CPU, 32 Gi, 100 Gi, 250 conn | 8 CPU, 32 Gi, 32 Gi |
| 1500  | 8 CPU, 32 Gi, 100 Gi, 300 conn | 8 CPU, 32 Gi, 32 Gi |

If you change pods or workers, recalculate **max_connections**: (pods × workers × 10) + reserve.

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
