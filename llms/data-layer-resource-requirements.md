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

## Storage: what does it mean, and how do production projects handle it?

If you don’t have much production experience, it’s normal to wonder: “50 Gi — is that for one month? What exactly am I allocating?”

### What are you allocating?

- **50 Gi** (or 100 Gi) is the **total size of the disk** you give to PostgreSQL (or Redis) via a **PVC** (Persistent Volume Claim).
- It is **not** “50 Gi per month.” It is **one volume of 50 Gi**. Data (e.g. spend logs) **accumulates** on that volume over time. So:
  - **50 Gi for PostgreSQL (700 users):** With roughly ~20 requests/sec and ~1–2 KB per log row, you can store on the order of **tens of days to a few months** of spend logs, depending on how many requests you actually do and whether you delete or archive old data.
  - **100 Gi for PostgreSQL (1000–1500 users):** Same idea, but more traffic → more rows per day → 100 Gi gives you roughly **30–60+ days** of logs if you don’t delete anything, or longer if you archive/compress or have lower traffic.

So: **the number (50 Gi or 100 Gi) is the capacity of the disk. How long it “lasts” depends on how much data you write per day and whether you keep data forever or apply a retention policy.**

### How long does 50 Gi last? (rough idea)

| Tier   | Approx. traffic | Approx. log growth | 50 Gi holds (no deletion) |
|--------|------------------|--------------------|----------------------------|
| 700 users  | ~20 req/sec peak | ~2–5 Gi per 30 days | ~10–25 months (order of magnitude) |
| 1000–1500 users | ~30–50 req/sec | ~5–15 Gi per 30 days | 100 Gi: ~2–6 months |

These are **rough** numbers; real size depends on row size, indexes, and other tables. The point: **50 Gi is not “for one month”** — it’s a pool that can hold many months of data at 700-user scale if you don’t delete, or you can limit retention (e.g. keep 90 days) and stay well under 50 Gi.

### How do production projects usually handle storage?

In normal production setups, teams do the following:

1. **Choose a retention period**  
   Decide how long to keep spend logs (e.g. 30, 90, or 365 days). Older data is either **deleted** or **moved to cold storage/archive**. That caps how much disk you need and keeps the database fast.

2. **Size for that retention**  
   Estimate “data per day” × “retention in days” × safety factor (e.g. 1.5), then allocate that much storage. So “50 Gi” in our table is a **reasonable starting capacity** that allows tens of days to several months of retention depending on traffic; you can shrink retention or grow the volume later.

3. **Monitor usage**  
   Use metrics (e.g. PostgreSQL disk usage, or Kubernetes PVC usage). Alert when usage goes above a threshold (e.g. 80%). That way you know **before** the disk is full.

4. **Expand when needed**  
   When the volume is filling up, you can **resize the PVC** (if your storage driver supports it) or **add a new volume** and move/archive data. So you don’t have to get the size perfect on day one; you can start with 50 Gi and grow later.

5. **Redis storage**  
   For Redis, the 20 Gi / 32 Gi we suggest are for **persistence** (RDB/AOF) if you enable it. Redis data is usually much smaller than PostgreSQL (counters, cache, buffer). If you don’t use persistence, Redis doesn’t need a large PVC; the numbers we give are for the “persistence enabled” case.

### Short answers

| Question | Answer |
|----------|--------|
| Is 50 Gi for one month? | No. 50 Gi is the **total disk size** you allocate. How many months it covers depends on your RPS and whether you delete old data. |
| How long does 50 Gi last? | Roughly **many months** at 700-user traffic if you keep everything; or **indefinitely** if you keep only e.g. 90 days and delete the rest. |
| What do production teams do? | They set a **retention period**, **size** storage for that period, **monitor** usage, and **resize or archive** when needed. |

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
