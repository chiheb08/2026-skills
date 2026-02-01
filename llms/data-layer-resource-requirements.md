# Data Layer Resource Requirements (PostgreSQL & Redis)

Resource parameters and values for the data layer only, by expected user count. Use these under your Deployment/Pod `resources` and PVC `storage`; `max_connections` is a PostgreSQL server config setting.

Based on [infrastructure-sizing-700-1500-users.md](./infrastructure-sizing-700-1500-users.md).

---

## Why these values? (Justification)

The numbers below are derived from **traffic and topology**, not guesswork. If your traffic or LiteLLM topology differs, adjust using the same logic.

### Traffic assumptions (from infrastructure sizing)

| Users | Peak RPS | Concurrent requests | LiteLLM replicas | Workers per pod (typical) |
|-------|----------|---------------------|------------------|---------------------------|
| 700   | 15–25    | 105–160             | 3                | 4                         |
| 1000  | 25–40    | 150–225             | 4–5              | 4                         |
| 1500  | 40–60    | 225–340             | 5–6              | 4                         |

- **Peak RPS** = requests per second at peak; drives DB write volume (spend logs) and Redis ops (rate limits, cache, buffer).
- **LiteLLM replicas × workers** = total workers; drives **total PostgreSQL connections** (each worker has its own pool).

---

### PostgreSQL — rationale

**CPU**

- PostgreSQL serves: (1) **reads** for key/team validation and spend checks — most are served from **Redis cache** after the first lookup; (2) **writes** for spend logs — at high RPS these go through the **Redis transaction buffer**, so the DB sees **batched, aggregated** writes from a **single** writer, not raw request volume.
- So **DB load in queries/sec** is much lower than **application RPS**. Rule of thumb: 1 vCPU per ~10–20 active connections and moderate query rate. At 700 users (15–25 RPS, ~12 workers) **4 vCPU** is enough. At 1000–1500 users (25–60 RPS, more workers and more batched writes) **8 vCPU** avoids CPU saturation and keeps latency stable.
- **Argument:** 4 vCPU for 700 users; 8 vCPU for 1000 and 1500 so the DB is not the bottleneck when RPS and connection count double.

**Memory**

- Used for: **shared_buffers** (cache of tables/indexes), **work_mem** (per-query sorts/joins), **connection overhead** (~few MB per connection).
- Common guidance: **shared_buffers ≈ 25% of RAM**; enough RAM for `max_connections` (each connection has a backend process and buffers). For **150 connections**, **16 Gi** is a standard starting point. For **250–300 connections** and a larger working set (e.g. `LiteLLM_SpendLogs` growing), **32 Gi** keeps cache hit rate high and avoids OOM.
- **Argument:** 16 Gi for 700 (up to 150 connections, smaller log volume); 32 Gi for 1000 and 1500 (more connections, more data, better cache).

**Storage**

- Growth is dominated by **spend logs** (one row per request, plus metadata). Rough order of magnitude: **~1–2 KB per row**; at **25 RPS** over **30 days**: 25 × 86 400 × 30 × 1.5 KB ≈ **97 Gi**. At **15 RPS** and 30 days: ~58 Gi; with 90-day retention or compression, **50 Gi** for 700 users is a reasonable starting point. For 1000–1500 users at 25–60 RPS, **100 Gi** allows 30–60 days retention without constant resizing.
- **Argument:** 50 Gi for 700 (lower RPS, shorter or compressed retention); 100 Gi for 1000 and 1500 (higher RPS, 30+ days retention).

**max_connections**

- **Total connections from LiteLLM** = `instances × workers_per_instance × database_connection_pool_limit`. You must set PostgreSQL `max_connections` **above** that total, plus **reserve for admin, migrations, and other apps**.
- Example: 700 users → 3 replicas × 4 workers × 10 pool = **120**; reserve **30** → **150**. 1000 users → 5 × 4 × 10 = **200**; reserve **50** → **250**. 1500 users → 6 × 4 × 10 = **240**; reserve **60** → **300**.
- **Argument:** Values 150 / 250 / 300 match the connection-pool formula in [litellm-data-layer-technical-challenges.md](./litellm-data-layer-technical-challenges.md) and leave headroom for non-LiteLLM connections.

---

### Redis — rationale

**CPU**

- Redis handles: **rate limit** checks/updates (every request), **cache** get/set (cache hits/misses), **transaction buffer** enqueue, and (when buffer is used) **lock** acquire/release. CPU scales roughly with **RPS** and **key count**.
- At **15–25 RPS**, 4 vCPU is enough for Redis to stay under ~50% utilization with headroom for spikes. At **25–60 RPS**, 8 vCPU keeps latency low and avoids the “single-threaded” bottleneck (Redis is mostly single-threaded per core; more cores help for background persistence and connection handling).
- **Argument:** 4 vCPU for 700 users; 8 vCPU for 1000 and 1500 so Redis is not the limiting factor when request volume doubles.

**Memory**

- Used for: **response cache** (and optional semantic cache), **rate limit counters** (small), **transaction buffer queue** (pending spend updates before flush to PostgreSQL), **metadata** (keys, expiry).
- Rule of thumb: **base ~2–4 Gi** + **~50–100 MB per 10 RPS** for cache and buffer. At 15–25 RPS, **16 Gi** is comfortable. At 25–60 RPS and larger cache/buffer, **32 Gi** avoids evictions and queue pressure.
- **Argument:** 16 Gi for 700; 32 Gi for 1000 and 1500 to support higher RPS and larger cache/buffer without hitting memory limits.

**Storage (PVC, if persistence enabled)**

- Only needed if you enable **RDB snapshots** or **AOF**. Size for **dump size + growth**. With 16 Gi RAM, dump can be on the order of a few Gi; with 32 Gi, up to ~10–15 Gi. **20 Gi** for 700 and **32 Gi** for 1000/1500 give room for dumps and growth without resizing often.
- **Argument:** 20 Gi for 700 (smaller dataset); 32 Gi for 1000 and 1500 (larger cache and buffer footprint).

---

### Summary: why each tier gets these values

| Users | Scenario in one line | PostgreSQL | Redis |
|-------|----------------------|------------|--------|
| 700   | Low RPS (15–25), 12 workers, batched writes | 4 vCPU / 16 Gi / 50 Gi / 150 conn — enough for connections and log volume | 4 vCPU / 16 Gi / 20 Gi — enough for cache, limits, buffer |
| 1000  | Mid RPS (25–40), ~20 workers, higher log volume | 8 vCPU / 32 Gi / 100 Gi / 250 conn — avoid CPU and connection exhaustion | 8 vCPU / 32 Gi / 32 Gi — match doubled RPS and cache |
| 1500  | High RPS (40–60), ~24 workers, same DB load shape as 1000 | 8 vCPU / 32 Gi / 100 Gi / 300 conn — same as 1000, more connections only | 8 vCPU / 32 Gi / 32 Gi — same as 1000; HA recommended |

**Strong arguments in one sentence:**  
Values are **bounded by** (1) **connection math** (workers × pool_limit → max_connections), (2) **RPS** (spend log volume → storage; Redis ops → CPU/RAM), and (3) **common DB/Redis sizing rules** (shared_buffers, connection overhead, cache/buffer size). If you change replicas, workers, or RPS, recompute using the same formulas and rules above.

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
