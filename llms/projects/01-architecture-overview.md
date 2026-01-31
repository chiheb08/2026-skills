# 1. Architecture Overview — Central LLM Platform (On-Prem OpenShift)

## 1.1 Design Principles

- **Single gateway:** All consumer apps call **LiteLLM** only; no direct access to vLLM or databases from apps.
- **On-prem only:** No external LLM APIs; all models served by **vLLM** in the cluster.
- **OpenShift:** All services run in OpenShift (on-prem datacenter).
- **Shared data layer:** **PostgreSQL** for persistent data (keys, teams, spend); **Redis** for cache, rate limiting, and load-balancing state.

## 1.2 Logical Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: CONSUMER APPLICATIONS (multiple namespaces or one shared)          │
│  [ RAG ] [ Code Support ] [ Translate Tool ] [ ... ]                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTPS / OpenAI-compatible API
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: CENTRAL GATEWAY                                                     │
│  [ LiteLLM Proxy ]  ← single entry point for all LLM traffic                 │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                           │
                    │ HTTP (internal)            │ TCP
                    ▼                           ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────────┐
│  LAYER 3: INFERENCE           │    │  LAYER 4: DATA                           │
│  [ vLLM Backend 1 ]           │    │  [ PostgreSQL ]  [ Redis ]                │
│  [ vLLM Backend 2 ]   ...     │    │  keys, teams,    cache, rate limits,     │
│  (one per model / replica)   │    │  spend           load-balancing state     │
└──────────────────────────────┘    └──────────────────────────────────────────┘
```

## 1.3 Service Arrays (High-Level)

### Consumer applications (call LiteLLM only)

| # | Service / App       | Purpose                    | Calls                    |
|---|---------------------|----------------------------|---------------------------|
| 1 | RAG                 | Retrieval-augmented Q&A    | LiteLLM (chat/embeddings)|
| 2 | Code Support        | Code completion, analysis  | LiteLLM (chat)           |
| 3 | Translate Tool      | Translation                | LiteLLM (chat)           |
| 4 | (Future apps)       | Other use cases            | LiteLLM                  |

### Central gateway

| # | Service    | Purpose                          | Replicas | Calls                    |
|---|------------|----------------------------------|----------|---------------------------|
| 1 | LiteLLM    | API gateway, routing, keys, limits | 3+     | vLLM, PostgreSQL, Redis  |

### Inference (vLLM)

| # | Service / Deployment   | Model / Role     | Replicas | Called by   |
|---|------------------------|------------------|----------|-------------|
| 1 | vLLM Llama 2 7B        | General chat     | 2        | LiteLLM     |
| 2 | vLLM CodeLlama 13B     | Code             | 2        | LiteLLM     |
| 3 | vLLM Mistral 7B        | General / fast   | 2        | LiteLLM     |
| 4 | vLLM Llama 2 70B      | Large model      | 1        | LiteLLM     |
| 5 | vLLM Embeddings       | Embeddings       | 1        | LiteLLM     |

### Data layer

| # | Service     | Role                          | Used by   |
|---|-------------|-------------------------------|-----------|
| 1 | PostgreSQL  | Keys, teams, users, spend     | LiteLLM   |
| 2 | Redis       | Cache, rate limits, LB state  | LiteLLM   |

## 1.4 Communication Summary

- **Consumer apps → LiteLLM:** HTTPS (or HTTP inside cluster); OpenAI-compatible API (`/v1/chat/completions`, `/v1/embeddings`, etc.). Auth via API key (virtual key from LiteLLM).
- **LiteLLM → vLLM:** HTTP (cluster-internal); same API shape. No auth (internal network).
- **LiteLLM → PostgreSQL:** TCP 5432; keys, teams, spend, schema. Credentials via env/secret.
- **LiteLLM → Redis:** TCP 6379; cache, rate-limit counters, load-balancing state. Credentials via env/secret.
- **Consumer apps do not** talk to vLLM, PostgreSQL, or Redis directly.

## 1.5 OpenShift Namespaces (Proposed)

| Namespace       | Contents                                      |
|----------------|-----------------------------------------------|
| `llm-platform`  | LiteLLM, vLLM backends, shared config         |
| `llm-data`     | PostgreSQL, Redis (or use existing DB namespace) |
| `rag`          | RAG application pods                           |
| `code-support` | Code support application pods                  |
| `translate`    | Translate tool pods                            |

Alternatively, all consumer apps can run in a single namespace (e.g. `apps`) with labels; the important point is **only LiteLLM** in `llm-platform` talks to vLLM, PostgreSQL, and Redis.

## 1.6 Data Flow (Simplified)

1. **Request:** User → Consumer App (e.g. RAG) → LiteLLM (with API key).
2. **Auth & limits:** LiteLLM checks key and rate limits (PostgreSQL + Redis).
3. **Route:** LiteLLM selects model and vLLM backend (using config + Redis for load).
4. **Inference:** LiteLLM → vLLM (HTTP); vLLM returns completion/embedding.
5. **Response:** LiteLLM → Consumer App → User.
6. **Side effects:** LiteLLM updates spend in PostgreSQL and cache/rate state in Redis.

All details for services, ports, and exact communication are in [02-services-inventory.md](./02-services-inventory.md) and [03-communication-matrix.md](./03-communication-matrix.md).
