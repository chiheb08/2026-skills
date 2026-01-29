# LiteLLM Local Models Architecture - Complete Guide

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Component Details](#3-component-details)
4. [Load Balancing Architecture](#4-load-balancing-architecture)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [OpenShift Deployment Architecture](#6-openshift-deployment-architecture)
7. [Network Architecture](#7-network-architecture)
8. [Request Routing Flow](#8-request-routing-flow)
9. [Failover and Resilience](#9-failover-and-resilience)

---

## 1. System Overview

### Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT SERVICES LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   RAG System │  │ Code Support │  │  Custom Apps │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                    ┌────────▼────────┐
                    │  LiteLLM Proxy  │
                    │  (API Gateway)  │
                    │  ┌───────────┐  │
                    │  │  Router   │  │
                    │  │  Load Bal │  │
                    │  │  Rate Lim │  │
                    │  └───────────┘  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│  vLLM Backend │  │  vLLM Backend   │  │  vLLM Backend │
│  Llama 2 7B   │  │  CodeLlama 13B  │  │  Mistral 7B   │
│  (GPU Node)   │  │  (GPU Node)     │  │  (GPU Node)   │
└───────────────┘  └─────────────────┘  └───────────────┘
```

**Key Components:**
- **Client Services**: Applications that need LLM capabilities
- **LiteLLM Proxy**: Central API gateway with routing, load balancing, rate limiting
- **vLLM Backends**: Local inference engines running on GPU nodes
- **Supporting Services**: PostgreSQL (keys/spend), Redis (caching/load balancing)

---

## 2. High-Level Architecture

### Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OPENSHIFT CLUSTER                                 │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    NAMESPACE: llm-service                            │  │
│  │                                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │              LiteLLM Proxy Layer (Stateless)                 │   │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │   │  │
│  │  │  │ Pod 1    │  │ Pod 2    │  │ Pod 3    │                  │   │  │
│  │  │  │ (4 CPU)  │  │ (4 CPU)  │  │ (4 CPU)  │                  │   │  │
│  │  │  │ 8GB RAM  │  │ 8GB RAM  │  │ 8GB RAM  │                  │   │  │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │   │  │
│  │  │       └──────────────┼──────────────┘                        │   │  │
│  │  │                      │                                       │   │  │
│  │  │              ┌────────▼────────┐                             │   │  │
│  │  │              │  LiteLLM Service │                             │   │  │
│  │  │              │  (Load Balanced) │                             │   │  │
│  │  │              └────────┬────────┘                             │   │  │
│  │  └────────────────────────┼──────────────────────────────────────┘   │  │
│  │                           │                                           │  │
│  │  ┌────────────────────────┼──────────────────────────────────────┐   │  │
│  │  │        vLLM Backend Layer (Stateful - GPU Required)           │   │  │
│  │  │                           │                                     │   │  │
│  │  │  ┌───────────────────────┼───────────────────────┐            │   │  │
│  │  │  │                       │                       │            │   │  │
│  │  │  │  ┌──────────────┐  ┌─▼──────────┐  ┌───────▼──────┐     │   │  │
│  │  │  │  │ Llama 2 7B   │  │ CodeLlama  │  │ Mistral 7B   │     │   │  │
│  │  │  │  │ Pod 1 (GPU)  │  │ 13B Pod 1  │  │ Pod 1 (GPU)  │     │   │  │
│  │  │  │  └──────┬───────┘  │ (GPU)      │  │              │     │   │  │
│  │  │  │         │          └────────────┘  └──────────────┘     │   │  │
│  │  │  │  ┌──────▼───────┐                                       │   │  │
│  │  │  │  │ Llama 2 7B   │                                       │   │  │
│  │  │  │  │ Pod 2 (GPU)  │  (Load Balanced Instances)           │   │  │
│  │  │  │  └──────────────┘                                       │   │  │
│  │  │  └──────────────────────────────────────────────────────────┘   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  │                                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │              Supporting Services Layer                       │   │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │   │  │
│  │  │  │ PostgreSQL   │  │    Redis     │  │  Monitoring  │     │   │  │
│  │  │  │ (Keys/Spend) │  │ (Cache/LB)  │  │  (Prometheus) │     │   │  │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘     │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    External Access (Route)                            │ │
│  │  https://litellm.apps.openshift.example.com                            │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Details

### LiteLLM Proxy Internal Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LiteLLM Proxy Pod                              │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    FastAPI Application                     │  │
│  │  ┌───────────────────────────────────────────────────────┐ │  │
│  │  │              Request Handler                          │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐                 │ │  │
│  │  │  │ Auth Check   │→ │ Rate Limiter │                 │ │  │
│  │  │  │ (Virtual Key)│  │ (Redis)      │                 │ │  │
│  │  │  └──────────────┘  └──────┬───────┘                 │ │  │
│  │  │                           │                           │ │  │
│  │  │                  ┌────────▼────────┐                 │ │  │
│  │  │                  │  Model Router   │                 │ │  │
│  │  │                  │  (Load Balancer)│                 │ │  │
│  │  │                  └────────┬────────┘                 │ │  │
│  │  │                           │                           │ │  │
│  │  │                  ┌────────▼────────┐                 │ │  │
│  │  │                  │  vLLM Client    │                 │ │  │
│  │  │                  │  (OpenAI Compat)│                 │ │  │
│  │  │                  └────────┬────────┘                 │ │  │
│  │  └──────────────────────────┼───────────────────────────┘ │  │
│  │                             │                               │  │
│  │  ┌──────────────────────────▼───────────────────────────┐   │  │
│  │  │              Response Handler                        │   │  │
│  │  │  ┌──────────────┐  ┌──────────────┐                │   │  │
│  │  │  │ Cost Tracking│→ │ Cache Store   │                │   │  │
│  │  │  │ (PostgreSQL) │  │ (Redis)       │                │   │  │
│  │  │  └──────────────┘  └──────────────┘                │   │  │
│  │  └───────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │              Health Check App (Separate Process)              │ │
│  │  Port: 8001  (Isolated from main app)                        │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### vLLM Backend Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    vLLM Backend Pod (GPU Node)                   │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              vLLM OpenAI-Compatible Server                │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │            Request Queue                           │  │  │
│  │  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐          │  │  │
│  │  │  │ Req1 │  │ Req2 │  │ Req3 │  │ Req4 │  ...     │  │  │
│  │  │  └──────┘  └──────┘  └──────┘  └──────┘          │  │  │
│  │  └──────────────────┬──────────────────────────────────┘  │  │
│  │                     │                                      │  │
│  │  ┌──────────────────▼──────────────────────────────────┐  │  │
│  │  │         Continuous Batching Engine                   │  │  │
│  │  │  ┌────────────────────────────────────────────────┐ │  │  │
│  │  │  │  Batch Requests Dynamically                    │ │  │  │
│  │  │  │  (PagedAttention for KV Cache)                 │ │  │  │
│  │  │  └──────────────────┬─────────────────────────────┘ │  │  │
│  │  └─────────────────────┼───────────────────────────────┘  │  │
│  │                         │                                    │  │
│  │  ┌───────────────────────▼───────────────────────────────┐   │  │
│  │  │              GPU Inference Engine                     │   │  │
│  │  │  ┌────────────────────────────────────────────────┐  │   │  │
│  │  │  │  Model Weights (Loaded in GPU Memory)          │  │   │  │
│  │  │  │  ┌──────────────┐                             │  │   │  │
│  │  │  │  │ Transformer  │                             │  │   │  │
│  │  │  │  │ Layers       │                             │  │   │  │
│  │  │  │  └──────────────┘                             │  │   │  │
│  │  │  │  ┌──────────────┐                             │  │   │  │
│  │  │  │  │ KV Cache     │ (PagedAttention)            │  │   │  │
│  │  │  │  └──────────────┘                             │  │   │  │
│  │  │  └────────────────────────────────────────────────┘  │   │  │
│  │  └───────────────────────┬───────────────────────────────┘   │  │
│  │                          │                                     │  │
│  │  ┌───────────────────────▼───────────────────────────────┐   │  │
│  │  │              Response Handler                          │   │  │
│  │  │  Stream responses back to LiteLLM                     │   │  │
│  │  └───────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Resources:                                                          │
│  - GPU: 1x NVIDIA A100 (or equivalent)                              │
│  - Memory: 80-100GB                                                 │
│  - Model Storage: PersistentVolume (500GB+)                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Load Balancing Architecture

### Load Balancing Across Multiple Instances

```
                    Client Request: "llama-2-7b"
                              │
                              ▼
                    ┌─────────────────────┐
                    │  LiteLLM Router     │
                    │  (simple-shuffle)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │  Weighted Selection  │
                    │  (Based on rpm/tpm) │
                    └──────────┬──────────┘
                               │
        ┌───────────────────────┼───────────────────────┐
        │                       │                         │
        ▼                       ▼                         ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ vLLM Instance │      │ vLLM Instance │      │ vLLM Instance │
│ Llama 2 7B #1 │      │ Llama 2 7B #2 │      │ Llama 2 7B #3 │
│               │      │               │      │               │
│ rpm: 600      │      │ rpm: 600      │      │ rpm: 600      │
│ tpm: 50000    │      │ tpm: 50000    │      │ tpm: 50000    │
│               │      │               │      │               │
│ Load: 45%     │      │ Load: 30%     │      │ Load: 25%     │
└───────────────┘      └───────────────┘      └───────────────┘
        │                       │                         │
        └───────────────────────┼─────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Redis (Shared State)│
                    │  - Rate limit tracking│
                    │  - Load distribution  │
                    └───────────────────────┘
```

### Load Balancing Strategy: simple-shuffle

```
Request Flow:
1. Client → LiteLLM: "Use llama-2-7b"
2. LiteLLM Router checks Redis for current load
3. Router selects instance based on:
   - Current load (from Redis)
   - rpm/tpm capacity
   - Weighted random selection
4. Request forwarded to selected vLLM instance
5. Response streamed back through LiteLLM
6. Load metrics updated in Redis
```

---

## 5. Data Flow Diagrams

### Complete Request Flow

```
┌─────────────┐
│   Client    │
│  (RAG App)  │
└──────┬──────┘
       │
       │ 1. POST /v1/chat/completions
       │    {model: "llama-2-7b", messages: [...]}
       ▼
┌─────────────────────────────────────────────────────────┐
│              LiteLLM Proxy Pod                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step 2: Authentication                            │  │
│  │ - Check virtual key (from PostgreSQL)             │  │
│  │ - Validate rate limits (from Redis)               │  │
│  └──────────────────┬────────────────────────────────┘  │
│                     │                                    │
│  ┌──────────────────▼────────────────────────────────┐  │
│  │ Step 3: Model Routing                              │  │
│  │ - Parse model name: "llama-2-7b"                  │  │
│  │ - Check Redis for available instances             │  │
│  │ - Select instance (load balancing)                │  │
│  └──────────────────┬────────────────────────────────┘  │
│                     │                                    │
│  ┌──────────────────▼────────────────────────────────┐  │
│  │ Step 4: Request Forwarding                       │  │
│  │ - Transform to OpenAI format                     │  │
│  │ - Forward to selected vLLM backend              │  │
│  └──────────────────┬────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────┘
                      │
                      │ 5. HTTP POST to vLLM
                      ▼
┌─────────────────────────────────────────────────────────┐
│              vLLM Backend Pod                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step 6: Request Processing                        │  │
│  │ - Add to continuous batching queue               │  │
│  │ - Batch with other requests                       │  │
│  │ - Run inference on GPU                            │  │
│  └──────────────────┬────────────────────────────────┘  │
│                     │                                    │
│  ┌──────────────────▼────────────────────────────────┐  │
│  │ Step 7: Response Generation                      │  │
│  │ - Stream tokens back                              │  │
│  │ - Return to LiteLLM                              │  │
│  └──────────────────┬────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────┘
                      │
                      │ 8. Stream Response
                      ▼
┌─────────────────────────────────────────────────────────┐
│              LiteLLM Proxy Pod                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step 9: Response Processing                      │  │
│  │ - Stream to client                                │  │
│  │ - Update cost tracking (PostgreSQL)               │  │
│  │ - Cache response (Redis)                          │  │
│  │ - Update rate limit counters (Redis)              │  │
│  └──────────────────┬────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────┘
                      │
                      │ 10. Final Response
                      ▼
┌─────────────┐
│   Client    │
│  (RAG App)  │
└─────────────┘
```

### Caching Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ Request
       ▼
┌─────────────────┐
│  LiteLLM Proxy  │
└──────┬──────────┘
       │
       │ 1. Check Cache
       ▼
┌─────────────────┐      Cache Hit?      ┌──────────────┐
│  Redis Cache    │◄─────────────────────┤  Return     │
│                 │      YES              │  Cached     │
└─────────────────┘                       │  Response   │
       │                                  └──────────────┘
       │ Cache Miss?
       │ NO
       ▼
┌─────────────────┐
│  vLLM Backend   │
│  (Inference)    │
└──────┬──────────┘
       │
       │ Response
       ▼
┌─────────────────┐
│  LiteLLM Proxy  │
└──────┬──────────┘
       │
       │ 2. Store in Cache
       ▼
┌─────────────────┐
│  Redis Cache    │
│  (TTL: config)  │
└─────────────────┘
```

---

## 6. OpenShift Deployment Architecture

### Complete OpenShift Resource Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OpenShift Cluster                                 │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              Namespace: llm-service                              │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  Deployment: litellm-proxy (3 replicas)                 │  │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │ │
│  │  │  │ Pod 1    │  │ Pod 2    │  │ Pod 3    │             │  │ │
│  │  │  │          │  │          │  │          │             │  │ │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘             │  │ │
│  │  │       └──────────────┼──────────────┘                  │  │ │
│  │  │                      │                                  │  │ │
│  │  │              ┌───────▼────────┐                        │  │ │
│  │  │              │ Service:       │                        │  │ │
│  │  │              │ litellm-service│                        │  │ │
│  │  │              │ (ClusterIP)    │                        │  │ │
│  │  │              └───────┬────────┘                        │  │ │
│  │  │                      │                                  │  │ │
│  │  │              ┌───────▼────────┐                        │  │ │
│  │  │              │ Route:         │                        │  │ │
│  │  │              │ litellm-route  │                        │  │ │
│  │  │              │ (External)     │                        │  │ │
│  │  └──────────────┼──────────────────────────────────────────┘  │ │
│  │                 │                                              │ │
│  │  ┌──────────────▼──────────────────────────────────────────┐  │ │
│  │  │  Deployment: vllm-llama-2-7b (2 replicas)              │  │ │
│  │  │  ┌──────────┐  ┌──────────┐                            │  │ │
│  │  │  │ Pod 1    │  │ Pod 2    │                            │  │ │
│  │  │  │ (GPU)    │  │ (GPU)    │                            │  │ │
│  │  │  └────┬─────┘  └────┬─────┘                            │  │ │
│  │  │       └──────────────┼──────────────────┘              │  │ │
│  │  │                      │                                  │  │ │
│  │  │              ┌───────▼────────┐                        │  │ │
│  │  │              │ Service:       │                        │  │ │
│  │  │              │ vllm-llama-2-  │                        │  │ │
│  │  │              │ 7b-service     │                        │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  ConfigMap: litellm-config                             │  │ │
│  │  │  - config.yaml (model configuration)                   │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  Secrets:                                                │  │ │
│  │  │  - litellm-secrets (master_key, salt_key, db_url)       │  │ │
│  │  │  - redis-secrets (host, port, password)                 │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  PersistentVolumeClaim: model-storage-pvc                │  │ │
│  │  │  - Shared model storage (ReadWriteMany)                 │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  HorizontalPodAutoscaler: litellm-hpa                   │  │ │
│  │  │  - Auto-scale based on CPU/Memory                        │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Namespace: database (or external)                              │ │
│  │  ┌──────────────┐  ┌──────────────┐                            │ │
│  │  │ PostgreSQL   │  │    Redis     │                            │ │
│  │  │ Deployment   │  │  Deployment  │                            │ │
│  │  └──────────────┘  └──────────────┘                            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### Service Discovery

```
┌─────────────────────────────────────────────────────────────┐
│  Kubernetes DNS Resolution                                  │
│                                                              │
│  Service Name Format:                                       │
│  <service-name>.<namespace>.svc.cluster.local                │
│                                                              │
│  Examples:                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ litellm-service.llm-service.svc.cluster.local       │  │
│  │ → Routes to LiteLLM Proxy pods                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ vllm-llama-2-7b-service.llm-service.svc.cluster.local│  │
│  │ → Routes to vLLM Llama 2 7B pods                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ redis-service.redis.svc.cluster.local                │  │
│  │ → Routes to Redis pods                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Network Architecture

### Network Policies and Traffic Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Network Architecture                          │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  External Clients                                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                │  │
│  │  │ RAG App  │  │ Code App │  │ Web App  │                │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘                │  │
│  │       └─────────────┼──────────────┘                     │  │
│  │                     │                                      │  │
│  │                     │ HTTPS (TLS)                         │  │
│  │                     ▼                                      │  │
│  │            ┌─────────────────┐                            │  │
│  │            │  OpenShift Route │                            │  │
│  │            │  (Edge TLS)      │                            │  │
│  │            └────────┬─────────┘                            │  │
│  └─────────────────────┼──────────────────────────────────────┘  │
│                        │                                          │
│  ┌─────────────────────▼──────────────────────────────────────┐  │
│  │  Network Policy: Allow ingress from Route                  │  │
│  └─────────────────────┬──────────────────────────────────────┘  │
│                        │                                          │
│  ┌─────────────────────▼──────────────────────────────────────┐  │
│  │  LiteLLM Service (ClusterIP)                                │  │
│  │  Port: 4000                                                 │  │
│  └─────────────────────┬──────────────────────────────────────┘  │
│                        │                                          │
│  ┌─────────────────────▼──────────────────────────────────────┐  │
│  │  Network Policy: Allow egress to vLLM, Redis, PostgreSQL  │  │
│  └─────────────────────┬──────────────────────────────────────┘  │
│                        │                                          │
│        ┌───────────────┼───────────────┐                          │
│        │               │               │                          │
│        ▼               ▼               ▼                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│  │ vLLM     │  │  Redis   │  │PostgreSQL│                        │
│  │ Service  │  │ Service  │  │ Service  │                        │
│  │ :8000    │  │ :6379    │  │ :5432    │                        │
│  └──────────┘  └──────────┘  └──────────┘                        │
└───────────────────────────────────────────────────────────────────┘
```

### Network Policy Configuration

```
Ingress Rules (Allow):
- From: OpenShift Route
- To: LiteLLM Service (port 4000)

Egress Rules (Allow):
- From: LiteLLM Pods
- To: vLLM Services (port 8000)
- To: Redis Service (port 6379)
- To: PostgreSQL Service (port 5432)

Egress Rules (Deny):
- All other traffic (default deny)
```

---

## 8. Request Routing Flow

### Detailed Routing Decision Tree

```
                    Client Request Arrives
                            │
                            ▼
              ┌─────────────────────────┐
              │  Parse Request          │
              │  - Extract model name    │
              │  - Extract API key      │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  Authentication          │
              │  Check virtual key       │
              └───────────┬─────────────┘
                          │
                    ┌─────┴─────┐
                    │           │
              Valid?│           │Invalid
                    │           │
                    ▼           ▼
        ┌───────────────┐  ┌──────────┐
        │ Check Rate    │  │ Return   │
        │ Limits        │  │ 401      │
        │ (Redis)       │  └──────────┘
        └───────┬───────┘
                │
          ┌─────┴─────┐
          │           │
    Within Limit?│   │Exceeded
          │           │
          ▼           ▼
┌───────────────┐  ┌──────────┐
│ Find Model    │  │ Return   │
│ in Config     │  │ 429      │
└───────┬───────┘  └──────────┘
        │
  ┌─────┴─────┐
  │           │
Found?│       │Not Found
  │           │
  ▼           ▼
┌──────────┐  ┌──────────┐
│ Get      │  │ Return   │
│ Instances│  │ 404      │
│ (Redis)  │  └──────────┘
└────┬─────┘
     │
     ▼
┌─────────────────────────┐
│ Load Balancing          │
│ Strategy: simple-shuffle│
│                         │
│ 1. Get all instances    │
│ 2. Check load (Redis)   │
│ 3. Weighted selection   │
│ 4. Select instance      │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Forward Request         │
│ to Selected vLLM        │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Wait for Response       │
│ (Stream)                │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Process Response        │
│ - Stream to client      │
│ - Update costs (DB)     │
│ - Cache (Redis)        │
│ - Update counters      │
└─────────────────────────┘
```

---

## 9. Failover and Resilience

### Failover Architecture

```
                    Normal Operation
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  LiteLLM Router                   │
        │  Routes to: vLLM Instance #1     │
        └──────────────┬────────────────────┘
                       │
                       ▼
        ┌───────────────────────────────────┐
        │  vLLM Instance #1                 │
        │  Status: Healthy                   │
        │  Load: 60%                         │
        └───────────────────────────────────┘

                    Failure Detected
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  LiteLLM Router                    │
        │  Detects: Timeout/Error            │
        │  Action: Mark instance unhealthy   │
        └──────────────┬────────────────────┘
                       │
                       ▼
        ┌───────────────────────────────────┐
        │  Update Redis                      │
        │  - Mark instance as down           │
        │  - Remove from load balancer        │
        └──────────────┬────────────────────┘
                       │
                       ▼
        ┌───────────────────────────────────┐
        │  Retry with Fallback              │
        │  Routes to: vLLM Instance #2       │
        └──────────────┬────────────────────┘
                       │
                       ▼
        ┌───────────────────────────────────┐
        │  vLLM Instance #2                  │
        │  Status: Healthy                   │
        │  Load: 40% → 70%                   │
        └───────────────────────────────────┘

                    Model-Level Fallback
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  If all instances fail:          │
        │  Fallback to: llama-2-7b         │
        │  (from llama-2-70b)               │
        └──────────────────────────────────┘
```

### Health Check Flow

```
┌─────────────────────────────────────────────────────────┐
│  LiteLLM Health Check Architecture                      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Main Application (Port 4000)                    │  │
│  │  - Handles API requests                          │  │
│  │  - May be under heavy load                       │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                              │
│  ┌──────────────────────▼──────────────────────────┐  │
│  │  Separate Health App (Port 8001)                 │  │
│  │  - Lightweight FastAPI app                      │  │
│  │  - Isolated from main app                       │  │
│  │  - Always responsive                            │  │
│  └──────────────────────┬──────────────────────────┘  │
│                          │                              │
│  ┌──────────────────────▼──────────────────────────┐  │
│  │  Kubernetes Probes                              │  │
│  │  - Liveness: /health/liveliness                 │  │
│  │  - Readiness: /health/readiness                │  │
│  │  - Always return 200 OK                         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Resilience Features

```
┌─────────────────────────────────────────────────────────┐
│  Resilience Mechanisms                                  │
│                                                          │
│  1. Multiple Instances                                   │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│     │ Instance │  │ Instance │  │ Instance │          │
│     │    #1    │  │    #2    │  │    #3    │          │
│     └──────────┘  └──────────┘  └──────────┘          │
│                                                          │
│  2. Automatic Failover                                  │
│     Instance fails → Route to next instance             │
│                                                          │
│  3. Model-Level Fallback                                │
│     llama-2-70b fails → Fallback to llama-2-7b         │
│                                                          │
│  4. Graceful Degradation                                │
│     DB unavailable → Continue serving (VPC mode)        │
│                                                          │
│  5. Retry Logic                                         │
│     Request fails → Retry up to 3 times                │
│                                                          │
│  6. Circuit Breaker                                     │
│     Model fails 3+ times → Cooldown for 1 minute       │
└─────────────────────────────────────────────────────────┘
```

---

## Summary

This architecture provides:

✅ **High Availability**: Multiple instances of both LiteLLM and vLLM  
✅ **Load Balancing**: Intelligent distribution across instances  
✅ **Resilience**: Automatic failover and fallback mechanisms  
✅ **Scalability**: Horizontal scaling of stateless components  
✅ **Performance**: Redis caching, connection pooling, optimized routing  
✅ **Security**: Network policies, secrets management, authentication  
✅ **Observability**: Health checks, monitoring, logging  

All components are designed to work together seamlessly in an OpenShift on-premise datacenter environment.
