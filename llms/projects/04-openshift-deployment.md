# 4. OpenShift Deployment — Namespaces, Deployments, Services, Routes

Complete deployment layout for the central LLM platform on OpenShift (on-prem).

---

## 4.1 Namespaces (Array)

| # | Namespace     | Purpose |
|---|---------------|---------|
| 1 | llm-platform  | LiteLLM proxy, all vLLM backends, config, routes |
| 2 | llm-data      | PostgreSQL, Redis |
| 3 | rag           | RAG application |
| 4 | code-support  | Code support application |
| 5 | translate     | Translate tool |

**Create:**

```bash
oc create namespace llm-platform
oc create namespace llm-data
oc create namespace rag
oc create namespace code-support
oc create namespace translate
```

---

## 4.2 llm-platform — Resources

### Deployments (Array)

| # | Name              | Image (example)                    | Replicas | CPU (req/lim) | Memory (req/lim) | Notes |
|---|-------------------|------------------------------------|----------|---------------|-------------------|-------|
| 1 | litellm-proxy     | docker.litellm.ai/berriai/litellm-database:main-stable | 3 | 2/4 | 4Gi/8Gi | Args: --port 4000 --config /app/config.yaml --num_workers $(nproc) |
| 2 | vllm-llama-2-7b   | vllm/vllm-openai:latest            | 2        | -             | 80Gi/100Gi        | 1 GPU per pod |
| 3 | vllm-codellama-13b| vllm/vllm-openai:latest            | 2        | -             | 80Gi/100Gi        | 1 GPU per pod |
| 4 | vllm-mistral-7b   | vllm/vllm-openai:latest            | 2        | -             | 80Gi/100Gi        | 1 GPU per pod |
| 5 | vllm-llama-2-70b  | vllm/vllm-openai:latest            | 1        | -             | 160Gi/200Gi       | 2 GPU per pod |
| 6 | vllm-embeddings   | vllm/vllm-openai:latest (or custom) | 1       | -             | 16Gi/32Gi         | Embedding model |

### Services (Array)

| # | Name                      | Selector (example)     | Port | TargetPort |
|---|---------------------------|------------------------|------|------------|
| 1 | litellm-service           | app=litellm            | 4000 | 4000       |
| 2 | vllm-llama-2-7b-service   | app=vllm,model=llama-2-7b | 8000 | 8000    |
| 3 | vllm-codellama-13b-service| app=vllm,model=codellama-13b | 8000 | 8000 |
| 4 | vllm-mistral-7b-service   | app=vllm,model=mistral-7b | 8000 | 8000   |
| 5 | vllm-llama-2-70b-service  | app=vllm,model=llama-2-70b | 8000 | 8000  |
| 6 | vllm-embeddings-service   | app=vllm,model=embeddings | 8000 | 8000   |

### Routes

| # | Name           | Service           | Port | TLS        |
|---|----------------|-------------------|------|------------|
| 1 | litellm-route  | litellm-service   | 4000 | edge/redirect |

### ConfigMaps

| # | Name           | Content |
|---|----------------|--------|
| 1 | litellm-config | config.yaml (model_list, router_settings, litellm_settings, general_settings) |

### Secrets

| # | Name            | Keys (example) |
|---|-----------------|----------------|
| 1 | litellm-secrets | LITELLM_MASTER_KEY, LITELLM_SALT_KEY, DATABASE_URL |
| 2 | redis-secrets   | REDIS_HOST, REDIS_PORT, REDIS_PASSWORD |

### PersistentVolumeClaims

| # | Name               | Access      | Size   | Used by |
|---|--------------------|-------------|--------|---------|
| 1 | model-storage-pvc  | ReadWriteMany | 500Gi+ | vLLM deployments (model weights) |

### HorizontalPodAutoscaler

| # | Name         | Target           | Min | Max | Metrics (example) |
|---|--------------|------------------|-----|-----|--------------------|
| 1 | litellm-hpa  | litellm-proxy    | 3   | 10  | CPU 70%, Memory 80% |

---

## 4.3 llm-data — Resources

### Deployments / StatefulSets

| # | Name     | Type (example) | Port | Storage |
|---|----------|----------------|------|---------|
| 1 | postgres | StatefulSet or Deployment | 5432 | PVC for data |
| 2 | redis    | Deployment or StatefulSet | 6379 | Optional PVC |

### Services

| # | Name     | Port |
|---|----------|------|
| 1 | postgres | 5432 |
| 2 | redis    | 6379 |

### Secrets

| # | Name            | Purpose |
|---|-----------------|---------|
| 1 | postgres-credentials | POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB |
| 2 | redis-credentials   | REDIS_PASSWORD (REDIS_HOST/REDIS_PORT can be set to service name) |

**Note:** LiteLLM runs in `llm-platform` and needs to reach `postgres.llm-data.svc.cluster.local:5432` and `redis.llm-data.svc.cluster.local:6379`. Cross-namespace DNS is default in OpenShift.

---

## 4.4 Consumer App Namespaces (rag, code-support, translate)

Each namespace typically has:

- **Deployment:** Application pods (e.g. RAG backend, Code Support backend, Translate backend).
- **Service:** ClusterIP (or NodePort if needed) for the app.
- **Route (optional):** If the app is exposed to users.
- **Secret or ConfigMap:** `LITELLM_BASE_URL`, `LITELLM_API_KEY` (or inject key via secret).

No PostgreSQL or Redis in these namespaces for LLM platform use; only LiteLLM connection config.

---

## 4.5 Deployment Order

1. Create namespaces.
2. Deploy PostgreSQL and Redis in `llm-data`; create secrets and PVCs.
3. Create `litellm-config` ConfigMap and secrets in `llm-platform`.
4. Create model storage PVC in `llm-platform`.
5. Deploy vLLM backends (after model weights are available on the PVC or image).
6. Deploy LiteLLM proxy; create Service and Route.
7. Create NetworkPolicies (see [05-network-and-security.md](./05-network-and-security.md)).
8. Deploy consumer apps (RAG, Code Support, Translate) with LiteLLM URL and API key.

---

## 4.6 LiteLLM Config Reference

- **Config file:** Use the repo’s [litellm-config-local-models.yaml](../litellm-config-local-models.yaml) as base.
- **Service DNS in config:** Point each vLLM `api_base` to the corresponding service in `llm-platform`, e.g. `http://vllm-llama-2-7b-service.llm-platform.svc.cluster.local:8000/v1`.
- **PostgreSQL:** `DATABASE_URL=postgresql://<user>:<pass>@postgres.llm-data.svc.cluster.local:5432/litellm`
- **Redis:** `REDIS_HOST=redis.llm-data.svc.cluster.local`, `REDIS_PORT=6379`, `REDIS_PASSWORD` from secret.

All communication between these components is described in [03-communication-matrix.md](./03-communication-matrix.md).
