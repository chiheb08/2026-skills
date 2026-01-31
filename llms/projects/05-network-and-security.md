# 5. Network and Security — Policies, Secrets, and Access

Network policies, secrets, and security practices for the central LLM platform on OpenShift.

---

## 5.1 Network Policies (Array)

Policies restrict traffic so that only the intended callers can reach each service.

### Policy 1: LiteLLM — Egress to vLLM, PostgreSQL, Redis

- **Name:** allow-litellm-egress (or litellm-egress)
- **Namespace:** llm-platform
- **Selector:** Pods with label `app=litellm`
- **Type:** Egress
- **Allowed egress:**
  - To vLLM services in llm-platform (port 8000)
  - To PostgreSQL in llm-data (port 5432)
  - To Redis in llm-data (port 6379)
  - Optional: DNS (UDP 53) and external HTTPS if LiteLLM needs to reach outside (e.g. Slack webhook)

### Policy 2: LiteLLM — Ingress from Consumer Namespaces

- **Name:** allow-consumer-to-litellm
- **Namespace:** llm-platform
- **Selector:** Pods with label `app=litellm`
- **Type:** Ingress
- **Allowed ingress:**
  - From namespaces `rag`, `code-support`, `translate` (and any other consumer namespace) to port 4000
  - From OpenShift ingress/router (for Route) to port 4000

### Policy 3: vLLM — Ingress Only from LiteLLM

- **Name:** allow-litellm-to-vllm
- **Namespace:** llm-platform
- **Selector:** Pods with label `app=vllm`
- **Type:** Ingress
- **Allowed ingress:**
  - From pods with label `app=litellm` in llm-platform to port 8000

### Policy 4: PostgreSQL — Ingress Only from LiteLLM

- **Name:** allow-litellm-to-postgres
- **Namespace:** llm-data
- **Selector:** Pods for PostgreSQL (e.g. app=postgres)
- **Type:** Ingress
- **Allowed ingress:**
  - From namespace llm-platform, pods with label `app=litellm`, to port 5432

### Policy 5: Redis — Ingress Only from LiteLLM

- **Name:** allow-litellm-to-redis
- **Namespace:** llm-data
- **Selector:** Pods for Redis (e.g. app=redis)
- **Type:** Ingress
- **Allowed ingress:**
  - From namespace llm-platform, pods with label `app=litellm`, to port 6379

### Policy 6: Consumer Namespaces — Egress to LiteLLM Only (LLM traffic)

- **Name:** allow-egress-to-litellm
- **Namespace:** rag (and repeat for code-support, translate)
- **Selector:** App pods (e.g. app=rag)
- **Type:** Egress
- **Allowed egress:**
  - To namespace llm-platform, service litellm-service (port 4000)
  - DNS (UDP 53) and any other required egress (e.g. internal APIs, DBs used by the app itself — not LLM DB/Redis)

---

## 5.2 Secrets (Array)

| # | Secret Name       | Namespace   | Used by     | Keys / Content |
|---|-------------------|------------|-------------|----------------|
| 1 | litellm-secrets   | llm-platform | LiteLLM  | LITELLM_MASTER_KEY, LITELLM_SALT_KEY, DATABASE_URL |
| 2 | redis-secrets     | llm-platform | LiteLLM  | REDIS_HOST, REDIS_PORT, REDIS_PASSWORD |
| 3 | postgres-credentials | llm-data  | PostgreSQL | POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB |
| 4 | redis-credentials   | llm-data  | Redis      | REDIS_PASSWORD |
| 5 | litellm-api-key  | rag         | RAG app    | LITELLM_BASE_URL, LITELLM_API_KEY (virtual key) |
| 6 | litellm-api-key  | code-support | Code Support | LITELLM_BASE_URL, LITELLM_API_KEY |
| 7 | litellm-api-key  | translate   | Translate  | LITELLM_BASE_URL, LITELLM_API_KEY |

- **LITELLM_MASTER_KEY:** Must start with `sk-`; used for admin (e.g. key generation). Store in secret; do not put in config file in plain text.
- **LITELLM_SALT_KEY:** Used to encrypt keys in DB; do not change after first use. Generate with a strong random value.
- **DATABASE_URL:** Full PostgreSQL URL for LiteLLM (e.g. `postgresql://user:pass@postgres.llm-data.svc.cluster.local:5432/litellm`).
- **REDIS_***:** Same Redis instance used by LiteLLM; REDIS_HOST can be `redis.llm-data.svc.cluster.local`.

---

## 5.3 Service Accounts and RBAC (Optional)

- **LiteLLM:** Default service account in llm-platform is sufficient unless you need to read secrets from another namespace (then use a dedicated SA and role/rolebinding).
- **Consumer apps:** Default SA; no need to access llm-platform secrets if LiteLLM URL and API key are provided via their own namespace secret or config.

---

## 5.4 TLS and External Access

- **LiteLLM Route:** Use TLS termination at edge (OpenShift default); client → Route (HTTPS) → LiteLLM (HTTP).
- **Internal:** LiteLLM ↔ vLLM, PostgreSQL, Redis can stay on TCP (optionally TLS for DB and Redis in strict environments).
- **PostgreSQL/Redis:** For on-prem, TLS can be enabled on the DB and Redis servers and connection strings adjusted (e.g. `?sslmode=require` for PostgreSQL).

---

## 5.5 Summary

- **Network:** Only consumer apps → LiteLLM; LiteLLM → vLLM, PostgreSQL, Redis. No consumer → vLLM/DB/Redis.
- **Secrets:** Stored in OpenShift Secrets; never in config files in git.
- **Policies:** Applied per namespace to enforce the communication matrix in [03-communication-matrix.md](./03-communication-matrix.md).

For exact YAML examples of NetworkPolicies and Secret creation, these can be added in a follow-up `manifests/` folder under `llms/projects` if needed.
