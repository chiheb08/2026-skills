# Infrastructure Sizing: 700–1500 Users (On-Premise, H200 GPUs)

This document provides infrastructure resource requirements for serving **700 to 1500 users** with the LiteLLM + vLLM on-premise solution, assuming **NVIDIA H200** GPUs are available.

---

## Table of Contents

1. [Assumptions and Methodology](#1-assumptions-and-methodology)
2. [NVIDIA H200 Quick Reference](#2-nvidia-h200-quick-reference)
3. [Technical Terms Explained (GPU & Infrastructure Basics)](#3-technical-terms-explained-gpu--infrastructure-basics)
4. [Sizing Summary by Tier](#4-sizing-summary-by-tier)
5. [Component-Level Resources](#5-component-level-resources)
6. [OpenShift Node Layout](#6-openshift-node-layout)
7. [Capacity and Headroom](#7-capacity-and-headroom)
8. [Configuration Tuning](#8-configuration-tuning)
9. [References](#9-references)

---

## 1. Assumptions and Methodology

### 1.1 User and Traffic Assumptions

| Parameter | 700 users (min) | 1000 users (mid) | 1500 users (max) |
|-----------|------------------|-------------------|-------------------|
| **Total users** | 700 | 1,000 | 1,500 |
| **Peak concurrent users** (10–15%) | 70–105 | 100–150 | 150–225 |
| **Concurrent requests** (1.5 req/user at peak) | 105–160 | 150–225 | 225–340 |
| **Peak requests/sec (RPS)** | 15–25 | 25–40 | 40–60 |
| **Peak tokens/sec (approx)** | 30k–50k | 50k–80k | 80k–120k |

- **Concurrent users**: Not all users are active at once; 10–15% is typical for internal enterprise tools.
- **Concurrent requests**: Each active user may have 1–2 requests (e.g. one streaming, one in queue).
- **RPS**: Derived from concurrent requests and average request duration (~5–15 s per completion).

### 1.2 Model Mix (Example)

| Model | Share of traffic | Use case |
|-------|------------------|----------|
| Llama 2/3 7B (or Mistral 7B) | ~50% | Chat, RAG, light tasks |
| CodeLlama 13B | ~25% | Code support |
| Mistral 7B (or second 7B) | ~15% | Translation, general |
| Llama 2 70B (or similar) | ~8% | Heavy reasoning |
| Embeddings | ~2% | RAG indexing, search |

### 1.3 Sizing Approach

- **GPU**: Sized for vLLM inference; H200 memory and throughput drive replica count.
- **CPU/RAM**: Sized for LiteLLM, PostgreSQL, Redis, and OpenShift control plane.
- **Headroom**: ~20–30% buffer for peaks and growth.

---

## 2. NVIDIA H200 Quick Reference

| Spec | H200 SXM 141 GB |
|------|------------------|
| **VRAM** | 141 GB HBM3e |
| **Memory bandwidth** | 4.8 TB/s |
| **FP8 Tensor** | ~3,958 TFLOPS |
| **LLM inference** | ~2× H100 in many workloads |
| **Typical use** | Single GPU for 7B/13B/70B (weights); concurrency limited by KV cache |

**Why H200 for this stack**

- 7B/13B models fit easily; KV cache uses most of the 141 GB for high concurrency.
- 70B fits on one H200 (weights ~140 GB); for high concurrency, 2× H200 (tensor parallel) is recommended.
- More VRAM per GPU means fewer GPUs for a given user count than with 80 GB GPUs.

---

## 3. Technical Terms Explained (GPU & Infrastructure Basics)

If you are new to GPUs or infrastructure sizing, this section explains the technical terms used in this document in plain language.

### 3.1 GPU Memory

- **VRAM (Video RAM)**  
  The GPU’s own memory. It is separate from your server’s main RAM (system memory). All model weights and working data for inference must fit in VRAM. When we say “141 GB H200”, we mean 141 GB of VRAM on that GPU.

- **HBM3e (High Bandwidth Memory 3 extended)**  
  The type of memory used on the H200. “High bandwidth” means data can move in and out of this memory very quickly. HBM is built in stacks next to the GPU chip (not as normal RAM sticks). **HBM3e** is a recent, fast generation of this technology. More bandwidth (e.g. 4.8 TB/s) means the GPU can feed itself data faster and run LLM inference more efficiently.

- **Memory bandwidth (e.g. 4.8 TB/s)**  
  How much data can be read from or written to GPU memory per second (here, 4.8 terabytes per second). For large models, this often matters as much as raw compute. Higher bandwidth = less time waiting for data = higher throughput.

### 3.2 Compute and Performance

- **TFLOPS (TeraFLOPS)**  
  “Trillion floating-point operations per second.” A measure of how many math operations the GPU can do per second. Higher TFLOPS = more compute power. For LLMs, both compute and memory bandwidth matter.

- **FP8 / Tensor cores**  
  **FP8** = 8-bit floating-point: a compact number format that uses less memory and can be computed faster than full precision (FP32). **Tensor cores** are parts of the GPU optimized for the kind of matrix math used in neural networks. “FP8 Tensor” performance (e.g. ~3,958 TFLOPS on H200) is the rate when using this fast, AI-oriented path.

- **7B / 13B / 70B (model size)**  
  The “B” stands for **billions of parameters**. Parameters are the learned numbers (weights) that define the model. A 7B model has about 7 billion parameters (~14 GB in FP16). Bigger models are usually more capable but need more VRAM and compute.

- **Model weights**  
  The stored parameters of the trained neural network (the “model file”). They must be loaded into GPU VRAM before inference. Size in GB ≈ (parameters × 2) for FP16, e.g. 7B ≈ 14 GB, 70B ≈ 140 GB.

### 3.3 LLM Inference Concepts

- **KV cache (Key-Value cache)**  
  During text generation, the model reuses previous computations. The **KV cache** stores these intermediate results in VRAM so it doesn’t recompute them for every new token. The more concurrent requests (and the longer the context), the more KV cache you need. **Concurrency is often limited by available VRAM for the KV cache**, not only by model weight size.

- **Tensor parallelism (TP)**  
  Splitting a single model across **multiple GPUs** so that each GPU holds part of the model and they work together on each request. E.g. “TP=2” means one logical model run on 2 GPUs. Used when the model is too large or when you want higher throughput than a single GPU can give.

- **Replica**  
  A separate copy of the same service (e.g. the same vLLM model running on another GPU). More replicas = more concurrent requests you can handle (and better availability). “2 replicas of 7B” = two GPUs each running the 7B model.

- **Concurrency**  
  How many requests are being processed at the same time (e.g. 100 concurrent requests = 100 generations in progress). Sizing is driven by peak concurrency and how much KV cache each request needs.

- **Throughput (req/s, tokens/s)**  
  **req/s** = requests per second (completed responses). **tokens/s** = tokens generated per second across all requests. Higher throughput means the system can serve more users or heavier use.

- **Embeddings**  
  A different kind of model that turns text into fixed-size vectors (lists of numbers) for search, RAG, or similarity. Usually smaller and lighter than chat models; often one GPU can serve both embeddings and a small chat model, or embeddings alone at high throughput.

### 3.4 Infrastructure and Sizing

- **vCPU (virtual CPU)**  
  A share of a physical CPU core. In virtual machines or containers, “8 vCPU” means the workload can use up to 8 CPU cores’ worth of compute. Used to size LiteLLM, PostgreSQL, Redis, and node capacity.

- **Gi / GiB (gibibyte)**  
   Gi = GiB = 1,024³ bytes (~1.074 GB). Commonly used for RAM, VRAM, and storage in technical specs. “16 Gi RAM” = 16 gibibytes of memory.

- **RPS (requests per second)**  
  Number of API requests (e.g. chat completions) the system handles per second. Used to dimension the gateway and backends.

- **RPM / TPM**  
  **RPM** = requests per minute; **TPM** = tokens per minute. Used for rate limiting (e.g. per user or per API key).

- **Node**  
  A single physical or virtual server in the cluster. “GPU node” = server with GPUs; “worker node” = server used for CPU workloads (LiteLLM, DB, Redis, etc.).

- **Pod**  
  The smallest deployable unit in Kubernetes/OpenShift: one or more containers sharing network and storage. One vLLM “replica” typically = one pod with one GPU.

- **HA (High Availability)**  
  Design so that if one instance fails, others take over. E.g. multiple LiteLLM replicas, Redis Sentinel, or PostgreSQL failover.

- **HPA (Horizontal Pod Autoscaler)**  
  A Kubernetes/OpenShift mechanism that adds or removes pod replicas based on CPU, memory, or custom metrics (e.g. RPS).

- **ReadWriteMany (RWX)**  
  A storage access mode where the same volume can be mounted by **many pods at once** (read and write). Used for shared model weights so multiple vLLM pods can load the same model without duplicating it per pod.

- **NVMe**  
  A fast interface for SSDs. “SSD/NVMe” in this doc means fast disk for databases and caches, to avoid I/O becoming a bottleneck.

- **SXM (H200 SXM)**  
  NVIDIA’s module form factor for datacenter GPUs: the GPU is on a board that plugs into a special socket (with NVLink), rather than a PCIe card. SXM variants often have slightly higher power and performance than PCIe (NVL) versions.

---

## 4. Sizing Summary by Tier

### 4.1 Tier 1: ~700 Users

| Resource | Quantity | Notes |
|----------|----------|--------|
| **H200 GPUs** | **6–8** | vLLM inference only |
| **GPU node CPU** | 32–64 vCPU | 2–4 nodes × 16–32 vCPU (with 1–2 H200 per node) |
| **GPU node RAM** | 256–512 GB | 128–256 GB per node |
| **LiteLLM (CPU)** | 8 vCPU, 16 Gi RAM | 3 replicas × ~2.5 vCPU, ~5 Gi |
| **PostgreSQL** | 4 vCPU, 16 Gi RAM | 1 instance |
| **Redis** | 4 vCPU, 16 Gi RAM | 1 instance (or HA pair) |
| **Total CPU (platform)** | 16 vCPU | LiteLLM + PG + Redis |
| **Total RAM (platform)** | 48 Gi | LiteLLM + PG + Redis |

### 4.2 Tier 2: ~1000 Users

| Resource | Quantity | Notes |
|----------|----------|--------|
| **H200 GPUs** | **10–12** | vLLM inference |
| **GPU node CPU** | 64–96 vCPU | 4–6 nodes |
| **GPU node RAM** | 512–768 GB | 128 GB per node |
| **LiteLLM (CPU)** | 12 vCPU, 24 Gi RAM | 4–5 replicas |
| **PostgreSQL** | 8 vCPU, 32 Gi RAM | 1 instance, more connections |
| **Redis** | 8 vCPU, 32 Gi RAM | 1 or HA |
| **Total CPU (platform)** | 28 vCPU | |
| **Total RAM (platform)** | 88 Gi | |

### 4.3 Tier 3: ~1500 Users

| Resource | Quantity | Notes |
|----------|----------|--------|
| **H200 GPUs** | **14–18** | vLLM inference |
| **GPU node CPU** | 96–144 vCPU | 6–9 nodes |
| **GPU node RAM** | 768 Gi–1.1 Ti | 128 GB per node |
| **LiteLLM (CPU)** | 16 vCPU, 32 Gi RAM | 5–6 replicas |
| **PostgreSQL** | 8 vCPU, 32 Gi RAM | 1 instance |
| **Redis** | 8 vCPU, 32 Gi RAM | HA recommended |
| **Total CPU (platform)** | 32 vCPU | |
| **Total RAM (platform)** | 96 Gi | |

### 4.4 One-Page Overview

| Component | 700 users | 1000 users | 1500 users |
|-----------|-----------|------------|------------|
| **H200 GPUs** | 6–8 | 10–12 | 14–18 |
| **vLLM replicas (total)** | 6–8 | 10–12 | 14–18 |
| **LiteLLM replicas** | 3 | 4–5 | 5–6 |
| **LiteLLM CPU/RAM** | 8 vCPU / 16 Gi | 12 vCPU / 24 Gi | 16 vCPU / 32 Gi |
| **PostgreSQL CPU/RAM** | 4 vCPU / 16 Gi | 8 vCPU / 32 Gi | 8 vCPU / 32 Gi |
| **Redis CPU/RAM** | 4 vCPU / 16 Gi | 8 vCPU / 32 Gi | 8 vCPU / 32 Gi |
| **Peak RPS (design)** | 15–25 | 25–40 | 40–60 |

---

## 5. Component-Level Resources

### 5.1 vLLM Inference (H200)

Sizing is driven by **concurrent requests per model** and **throughput per GPU**.

**Approximate sustained throughput (single H200, vLLM):**

| Model size | Typical throughput (req/s) | Notes |
|------------|----------------------------|--------|
| 7B (e.g. Llama 2/3, Mistral) | 25–40 | High concurrency; KV cache in 141 GB |
| 13B (e.g. CodeLlama) | 15–30 | Still high concurrency |
| 70B (e.g. Llama 2 70B) | 5–15 (1 GPU) / 10–20 (2 GPUs) | 1× H200 for weights; 2× H200 for more concurrency |

**GPU count by tier (example model mix):**

| Model | 700 users | 1000 users | 1500 users |
|-------|-----------|------------|------------|
| Llama 2/3 7B | 2× H200 (2 replicas) | 3× H200 (3 replicas) | 4× H200 (4 replicas) |
| CodeLlama 13B | 1× H200 (1 replica) | 2× H200 (2 replicas) | 2× H200 (2 replicas) |
| Mistral 7B | 1× H200 (1 replica) | 1× H200 (1 replica) | 2× H200 (2 replicas) |
| Llama 2 70B | 2× H200 (1 replica, TP=2) | 2× H200 (1 replica) | 4× H200 (2 replicas, TP=2) |
| Embeddings | 0.5–1× H200 (shared or dedicated) | 1× H200 | 1× H200 |
| **Total H200** | **6–7** | **9–10** | **13–14** |

- **TP** = tensor parallelism (multi-GPU per replica).
- Replicas provide both capacity and redundancy; round up to **6–8**, **10–12**, **14–18** for headroom.

**Per-pod resources (OpenShift):**

```yaml
# Example: vLLM 7B replica on H200
resources:
  limits:
    nvidia.com/gpu: "1"
    memory: "120Gi"
  requests:
    nvidia.com/gpu: "1"
    memory: "100Gi"
# CPU: 4–8 vCPU per pod (request/limit)
```

**Storage (model weights):**

- Shared ReadWriteMany volume or image registry.
- ~50–80 GB per 7B model, ~130–150 GB per 70B model.
- Total for 7B + 13B + 7B + 70B + embeddings: **~400–600 GiB** (with cache headroom).

---

### 5.2 LiteLLM Gateway (CPU)

- **Role**: Auth, routing, rate limiting, spend checks, Redis/PostgreSQL access.
- **Bottleneck**: CPU and connection handling, not GPU.

**Minimum per replica (LiteLLM docs):** 4 vCPU, 8 Gi RAM.  
**Recommended for 700–1500 users:**

| Tier | Replicas | CPU total | RAM total | Per replica (request/limit) |
|------|----------|-----------|-----------|-----------------------------|
| 700 users | 3 | 8 vCPU | 16 Gi | 2 vCPU / 4 vCPU, 4 Gi / 6 Gi |
| 1000 users | 4–5 | 12 vCPU | 24 Gi | 2.5 vCPU / 4 vCPU, 4 Gi / 6 Gi |
| 1500 users | 5–6 | 16 vCPU | 32 Gi | 3 vCPU / 4 vCPU, 5 Gi / 6 Gi |

- Use **Uvicorn workers** ≈ number of CPUs per pod (e.g. `--num_workers 4`).
- Enable **Redis** for rate limits, cache, and transaction buffer; use **host/port/password** (not `redis_url`) for best performance.

---

### 5.3 PostgreSQL

- **Role**: Virtual keys, teams, users, spend logs, metadata.
- **Load**: Reads (key/team validation, spend checks cached in Redis); writes (spend logs, batched).

**Connections:**  
`MAX_DB_CONNECTIONS = replicas × workers × per_worker`.  
Example: 4 replicas × 4 workers × 10 = 160. Set `max_connections` in PostgreSQL ≥ 200 (with buffer).

**Sizing:**

| Tier | vCPU | RAM | Storage | max_connections |
|------|------|-----|---------|------------------|
| 700 users | 4 | 16 Gi | 50 Gi | 150 |
| 1000 users | 8 | 32 Gi | 100 Gi | 250 |
| 1500 users | 8 | 32 Gi | 100 Gi | 300 |

- SSD/NVMe recommended for `LiteLLM_SpendLogs` and general throughput.

---

### 5.4 Redis

- **Role**: Rate limits (RPM/TPM), cache, load-balancing state, transaction buffer for spend writes.
- **Version**: 7.0+.

**Sizing:**

| Tier | vCPU | RAM | Storage | Notes |
|------|------|-----|---------|--------|
| 700 users | 4 | 16 Gi | 20 Gi | Single instance OK |
| 1000 users | 8 | 32 Gi | 32 Gi | Single or Sentinel |
| 1500 users | 8 | 32 Gi | 32 Gi | Sentinel/Cluster for HA |

- 16–32 Gi RAM is enough for counters, cache, and buffer for this RPS range.

---

## 6. OpenShift Node Layout

### 6.1 Node Roles

- **GPU nodes**: vLLM pods only (H200).
- **CPU nodes**: LiteLLM, PostgreSQL, Redis, and other platform services.

### 6.2 Example: 700-User Tier

| Node type | Count | vCPU | RAM | GPU | Purpose |
|-----------|-------|------|-----|-----|--------|
| GPU (H200) | 3–4 | 32 each | 256 Gi each | 2× H200 each | vLLM only |
| Worker (CPU) | 2–3 | 32 each | 128 Gi each | — | LiteLLM, PG, Redis, system |

- **Total H200**: 6–8.  
- **Total CPU**: 96–128 vCPU (GPU nodes) + 64–96 vCPU (workers) = 160–224 vCPU (includes OS and overhead).
- Platform (LiteLLM + PG + Redis) uses a small fraction; rest for OpenShift, monitoring, ingress.

### 6.3 Example: 1500-User Tier

| Node type | Count | vCPU | RAM | GPU | Purpose |
|-----------|-------|------|-----|-----|--------|
| GPU (H200) | 7–9 | 32 each | 256 Gi each | 2× H200 each | vLLM only |
| Worker (CPU) | 3–4 | 32 each | 128 Gi each | — | LiteLLM, PG, Redis |

- **Total H200**: 14–18.

### 6.4 Diagram (Logical)

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                  OpenShift Cluster (On-Prem)            │
                    ├─────────────────────────────────────────────────────────┤
                    │  GPU Nodes (H200)          │  CPU Worker Nodes          │
                    │  ┌─────┐ ┌─────┐ ┌─────┐   │  ┌─────────────────────┐   │
                    │  │vLLM │ │vLLM │ │vLLM │   │  │ LiteLLM (3–6 pods)  │   │
                    │  │ 7B  │ │13B  │ │70B  │   │  │ PostgreSQL (1)      │   │
                    │  └──┬──┘ └──┬──┘ └──┬──┘   │  │ Redis (1 or HA)     │   │
                    │     │       │       │       │  └──────────┬──────────┘   │
                    │     └───────┴───────┘       │             │              │
                    │             │               │             │              │
                    │     Internal Service DNS     │     Routes / Ingress       │
                    └─────────────┼───────────────┴─────────────┼──────────────┘
                                  │                             │
                                  └──────────────┬──────────────┘
                                                 │
                                    Users (700–1500) → LiteLLM → vLLM
```

---

## 7. Capacity and Headroom

- **Target**: Support peak concurrent users and RPS with ~20–30% headroom.
- **GPU headroom**: Extra H200(s) allow more concurrent 70B or 7B requests; add 1–2 GPUs per tier if you expect growth.
- **LiteLLM**: Scale replicas (HPA) on CPU or RPS; keep 3 replicas minimum for HA.
- **PostgreSQL**: Connection pool and `max_connections` must match LiteLLM replicas × workers.
- **Redis**: Monitor memory and connection count; scale memory or move to Sentinel/Cluster if you grow beyond 1500 users or add more gateways.

---

## 8. Configuration Tuning

### 8.1 vLLM (per model)

- **max_model_len**: Lower (e.g. 4096) increases concurrency; 8192 is a good default.
- **gpu_memory_utilization**: 0.90–0.95 to maximize KV cache on H200.
- **max_num_seqs**: 128–256; tune per model and context length.

### 8.2 LiteLLM

- **Redis**: Use `redis_host`, `redis_port`, `redis_password` (not `redis_url`).
- **use_redis_transaction_buffer**: `true` to batch spend writes and reduce DB load.
- **Workers**: `--num_workers $(nproc)` or equal to vCPU per pod.
- **proxy_batch_write_at**: e.g. 60 (seconds) to batch DB writes.

### 8.3 PostgreSQL

- **Connection pool**: `MAX_DB_CONNECTIONS / (replicas × workers)` per worker.
- **Shared_buffers**: e.g. 25% of RAM for dedicated DB node.

---

## 9. References

- [LiteLLM production practices](https://docs.litellm.ai/docs/proxy/prod)
- [vLLM parallelism and scaling](https://docs.vllm.ai/en/stable/serving/parallelism_scaling.html)
- [NVIDIA H200](https://www.nvidia.com/en-us/data-center/h200/)
- Project docs: `llms/projects/`, `litellm-teams-spend-architecture.md`, `litellm-production-configuration-guide.md`

---

## Quick Reference Table

| Users | H200 GPUs | LiteLLM (vCPU / Gi) | PostgreSQL (vCPU / Gi) | Redis (vCPU / Gi) |
|-------|-----------|---------------------|------------------------|--------------------|
| 700   | 6–8       | 8 / 16              | 4 / 16                 | 4 / 16             |
| 1000  | 10–12     | 12 / 24             | 8 / 32                 | 8 / 32             |
| 1500  | 14–18     | 16 / 32             | 8 / 32                 | 8 / 32             |

All infrastructure is on-premise; H200 counts and CPU/RAM above are for the LiteLLM + vLLM solution only (no external LLM APIs). Adjust model mix and replica counts to match your actual traffic and SLA.
