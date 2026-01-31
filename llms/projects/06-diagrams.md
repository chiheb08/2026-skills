# 6. Architecture Diagrams — Central LLM Platform

Mermaid diagrams for the full on-prem OpenShift architecture with LiteLLM, vLLM, PostgreSQL, and Redis.

---

## 6.1 High-Level — Layers and Service Arrays

```mermaid
graph TB
    subgraph Consumers["Consumer Applications"]
        RAG["RAG App"]
        Code["Code Support"]
        Translate["Translate Tool"]
    end

    subgraph Gateway["Central Gateway"]
        LiteLLM["LiteLLM Proxy"]
    end

    subgraph Inference["vLLM Inference"]
        V1["vLLM Llama 2 7B"]
        V2["vLLM CodeLlama 13B"]
        V3["vLLM Mistral 7B"]
        V4["vLLM Llama 2 70B"]
        V5["vLLM Embeddings"]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL)]
        Redis[(Redis)]
    end

    RAG -->|HTTPS :4000| LiteLLM
    Code -->|HTTPS :4000| LiteLLM
    Translate -->|HTTPS :4000| LiteLLM

    LiteLLM -->|HTTP :8000| V1
    LiteLLM -->|HTTP :8000| V2
    LiteLLM -->|HTTP :8000| V3
    LiteLLM -->|HTTP :8000| V4
    LiteLLM -->|HTTP :8000| V5

    LiteLLM -->|TCP :5432| PG
    LiteLLM -->|TCP :6379| Redis
```

---

## 6.2 OpenShift Namespaces and Services

```mermaid
graph TB
    subgraph NS_rag["Namespace: rag"]
        RAG["rag-app :8080"]
    end

    subgraph NS_code["Namespace: code-support"]
        Code["code-support-app :8080"]
    end

    subgraph NS_translate["Namespace: translate"]
        Trans["translate-app :8080"]
    end

    subgraph NS_llm["Namespace: llm-platform"]
        LiteLLM["litellm-service :4000"]
        V1["vllm-llama-2-7b-service :8000"]
        V2["vllm-codellama-13b-service :8000"]
        V3["vllm-mistral-7b-service :8000"]
        V4["vllm-llama-2-70b-service :8000"]
        V5["vllm-embeddings-service :8000"]
    end

    subgraph NS_data["Namespace: llm-data"]
        PG["postgres :5432"]
        Redis["redis :6379"]
    end

    RAG --> LiteLLM
    Code --> LiteLLM
    Trans --> LiteLLM
    LiteLLM --> V1
    LiteLLM --> V2
    LiteLLM --> V3
    LiteLLM --> V4
    LiteLLM --> V5
    LiteLLM --> PG
    LiteLLM --> Redis
```

---

## 6.3 Communication Flow — Single Request

```mermaid
sequenceDiagram
    participant User
    participant App as Consumer App (e.g. RAG)
    participant LiteLLM
    participant Redis
    participant DB as PostgreSQL
    participant vLLM

    User->>App: Request
    App->>LiteLLM: POST /v1/chat/completions (API key)
    LiteLLM->>Redis: Check cache / rate limits
    Redis-->>LiteLLM: OK / counters
    LiteLLM->>DB: Validate key (if needed)
    DB-->>LiteLLM: Key valid
    LiteLLM->>LiteLLM: Select model & vLLM backend
    LiteLLM->>vLLM: POST /v1/chat/completions
    vLLM-->>LiteLLM: Completion
    LiteLLM->>Redis: Update cache & counters
    LiteLLM->>DB: Update spend
    LiteLLM-->>App: Response
    App-->>User: Result
```

---

## 6.4 Network Policies — Allowed Directions

```mermaid
graph LR
    subgraph Allowed["Allowed traffic"]
        A1[Consumer apps] -->|:4000| L[LiteLLM]
        L -->|:8000| V[vLLM backends]
        L -->|:5432| P[PostgreSQL]
        L -->|:6379| R[Redis]
    end

    subgraph Blocked["No direct access"]
        A2[Consumer apps] -.->|blocked| V
        A2 -.->|blocked| P
        A2 -.->|blocked| R
    end
```

---

## 6.5 Data Flow — Redis and PostgreSQL

```mermaid
graph TB
    subgraph LiteLLM["LiteLLM"]
        Req[Request Handler]
        Router[Router]
        Cache[Cache Layer]
        RateLimit[Rate Limiter]
    end

    subgraph Redis["Redis"]
        CacheStore[Response cache]
        Counters[rpm/tpm counters]
        LBState[Load-balancing state]
    end

    subgraph PG["PostgreSQL"]
        Keys[Virtual keys]
        Teams[Teams / Users]
        Spend[Spend tracking]
    end

    Req --> RateLimit
    RateLimit --> Counters
    Req --> Cache
    Cache --> CacheStore
    Router --> LBState
    Req --> Keys
    Req --> Teams
    Req --> Spend
```

---

## 6.6 Deployment Array — llm-platform

```mermaid
graph TB
    subgraph Deployments["Deployments in llm-platform"]
        D1["litellm-proxy (3 replicas)"]
        D2["vllm-llama-2-7b (2)"]
        D3["vllm-codellama-13b (2)"]
        D4["vllm-mistral-7b (2)"]
        D5["vllm-llama-2-70b (1)"]
        D6["vllm-embeddings (1)"]
    end

    subgraph Config["Config"]
        CM[ConfigMap: litellm-config]
        S1[Secret: litellm-secrets]
        S2[Secret: redis-secrets]
    end

    subgraph Storage["Storage"]
        PVC[model-storage-pvc]
    end

    D1 --> CM
    D1 --> S1
    D1 --> S2
    D2 --> PVC
    D3 --> PVC
    D4 --> PVC
    D5 --> PVC
    D6 --> PVC
```

---

## 6.7 Full System — Services in Arrays (Summary)

| Layer        | Services (array) |
|-------------|-------------------|
| Consumers   | rag-app, code-support-app, translate-app |
| Gateway     | litellm-service |
| vLLM        | vllm-llama-2-7b-service, vllm-codellama-13b-service, vllm-mistral-7b-service, vllm-llama-2-70b-service, vllm-embeddings-service |
| Data        | postgres, redis |

All details: [01-architecture-overview.md](./01-architecture-overview.md), [02-services-inventory.md](./02-services-inventory.md), [03-communication-matrix.md](./03-communication-matrix.md).
