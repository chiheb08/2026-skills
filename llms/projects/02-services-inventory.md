# 2. Services Inventory — Complete List

Every service in the central LLM platform, with ports, dependencies, and configuration references.

---

## 2.1 Consumer Applications (Array)

These applications call **only LiteLLM**; they do not connect to vLLM, PostgreSQL, or Redis.

| # | Service Name   | Namespace   | Port (app) | Protocol | Config / Env |
|---|----------------|------------|------------|----------|--------------|
| 1 | rag-app        | rag        | 8080       | HTTP     | `LITELLM_BASE_URL`, `LITELLM_API_KEY` |
| 2 | code-support-app | code-support | 8080   | HTTP     | `LITELLM_BASE_URL`, `LITELLM_API_KEY` |
| 3 | translate-app  | translate  | 8080       | HTTP     | `LITELLM_BASE_URL`, `LITELLM_API_KEY` |

- **LITELLM_BASE_URL:** e.g. `https://litellm-route-llm-platform.apps.<cluster>/` or internal `http://litellm-service.llm-platform.svc.cluster.local:4000`
- **LITELLM_API_KEY:** Virtual key issued by LiteLLM (from UI or `/key/generate`).

---

## 2.2 Central Gateway (Array)

| # | Service Name | Namespace   | Port | Protocol | Replicas | Dependencies |
|---|--------------|------------|------|----------|----------|--------------|
| 1 | litellm-service | llm-platform | 4000 | HTTP     | 3+       | PostgreSQL, Redis, vLLM backends |

**Configuration:**
- **ConfigMap:** `litellm-config` (config.yaml with model_list, router_settings, litellm_settings, general_settings).
- **Secrets:** `litellm-secrets` (LITELLM_MASTER_KEY, LITELLM_SALT_KEY, DATABASE_URL), `redis-secrets` (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD).
- **Env:** LITELLM_MODE=PRODUCTION, LITELLM_LOG=ERROR, DISABLE_SCHEMA_UPDATE=true (if migrations run via hook).

**Optional:** Separate health app on port 8001 (SEPARATE_HEALTH_APP=1).

---

## 2.3 vLLM Inference Backends (Array)

All in namespace `llm-platform`. Each entry is a Deployment + Service.

| # | Deployment Name        | Service Name                  | Model / Purpose | Port | Replicas | Resources (example) |
|---|------------------------|-------------------------------|------------------|------|----------|----------------------|
| 1 | vllm-llama-2-7b        | vllm-llama-2-7b-service       | Llama 2 7B       | 8000 | 2        | 1 GPU, 80Gi RAM      |
| 2 | vllm-codellama-13b    | vllm-codellama-13b-service    | CodeLlama 13B    | 8000 | 2        | 1 GPU, 80Gi RAM      |
| 3 | vllm-mistral-7b       | vllm-mistral-7b-service       | Mistral 7B       | 8000 | 2        | 1 GPU, 80Gi RAM      |
| 4 | vllm-llama-2-70b      | vllm-llama-2-70b-service      | Llama 2 70B      | 8000 | 1        | 2 GPU, 160Gi RAM     |
| 5 | vllm-embeddings       | vllm-embeddings-service       | Embedding model  | 8000 | 1        | 1 GPU or CPU         |

**Internal URL pattern:** `http://<service-name>.llm-platform.svc.cluster.local:8000/v1`

**Storage:** PersistentVolumeClaim for model weights (e.g. ReadWriteMany, 500Gi+).

---

## 2.4 Data Layer (Array)

| # | Service Name   | Namespace | Port | Protocol | Purpose |
|---|----------------|-----------|------|----------|---------|
| 1 | postgres       | llm-data  | 5432 | TCP      | Keys, teams, users, spend tracking |
| 2 | redis          | llm-data  | 6379 | TCP      | Cache, rate limits, load-balancing state |

**PostgreSQL:**
- Database: e.g. `litellm`
- Used by: LiteLLM only (virtual keys, teams, spend).
- Connection string in secret: `DATABASE_URL`.

**Redis:**
- Used by: LiteLLM only (cache, rpm/tpm counters, routing state).
- Minimum version: 7.0.
- Credentials: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD (from secret).

---

## 2.5 OpenShift Infrastructure Objects (Reference)

| Type        | Name (example)     | Namespace   | Purpose |
|-------------|--------------------|------------|---------|
| Route       | litellm-route      | llm-platform | External HTTPS to LiteLLM |
| ConfigMap   | litellm-config     | llm-platform | LiteLLM config.yaml |
| Secret      | litellm-secrets   | llm-platform | Master key, salt, DB URL |
| Secret      | redis-secrets     | llm-platform | Redis connection |
| PVC         | model-storage-pvc | llm-platform | Shared model weights (vLLM) |
| HPA         | litellm-hpa       | llm-platform | Auto-scale LiteLLM |
| NetworkPolicy | allow-litellm-egress | llm-platform | Allow LiteLLM → vLLM, DB, Redis |

---

## 2.6 Summary Table (All Services in One Array)

| Category   | Service / Deployment   | Namespace   | Port | Calls / Called by |
|------------|------------------------|------------|------|--------------------|
| Consumer   | rag-app                | rag        | 8080 | → LiteLLM          |
| Consumer   | code-support-app       | code-support | 8080 | → LiteLLM        |
| Consumer   | translate-app           | translate  | 8080 | → LiteLLM          |
| Gateway    | litellm-service         | llm-platform | 4000 | → vLLM, PostgreSQL, Redis |
| Inference  | vllm-llama-2-7b        | llm-platform | 8000 | ← LiteLLM          |
| Inference  | vllm-codellama-13b     | llm-platform | 8000 | ← LiteLLM          |
| Inference  | vllm-mistral-7b        | llm-platform | 8000 | ← LiteLLM          |
| Inference  | vllm-llama-2-70b       | llm-platform | 8000 | ← LiteLLM          |
| Inference  | vllm-embeddings        | llm-platform | 8000 | ← LiteLLM          |
| Data       | postgres               | llm-data   | 5432 | ← LiteLLM          |
| Data       | redis                  | llm-data   | 6379 | ← LiteLLM          |

All communication details (protocols, ports, and allowed directions) are in [03-communication-matrix.md](./03-communication-matrix.md).
