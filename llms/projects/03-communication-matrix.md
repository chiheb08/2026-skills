# 3. Communication Matrix — How Services Talk to Each Other

This document defines **who talks to whom**, over **which protocol and port**, and **what data** is exchanged.

---

## 3.1 Communication Matrix (Table)

| Source (caller)     | Target (callee)   | Protocol | Port | Purpose |
|---------------------|-------------------|----------|------|---------|
| RAG app             | LiteLLM           | HTTP/HTTPS | 4000 | Chat, embeddings (OpenAI-compatible API) |
| Code Support app    | LiteLLM           | HTTP/HTTPS | 4000 | Chat completions |
| Translate app       | LiteLLM           | HTTP/HTTPS | 4000 | Chat completions |
| (Any consumer app)   | LiteLLM           | HTTP/HTTPS | 4000 | Same API |
| LiteLLM             | vLLM Llama 2 7B   | HTTP     | 8000 | /v1/chat/completions, /v1/embeddings |
| LiteLLM             | vLLM CodeLlama 13B| HTTP     | 8000 | /v1/chat/completions |
| LiteLLM             | vLLM Mistral 7B   | HTTP     | 8000 | /v1/chat/completions |
| LiteLLM             | vLLM Llama 2 70B  | HTTP     | 8000 | /v1/chat/completions |
| LiteLLM             | vLLM Embeddings   | HTTP     | 8000 | /v1/embeddings |
| LiteLLM             | PostgreSQL        | TCP      | 5432 | Keys, teams, users, spend (Prisma/SQL) |
| LiteLLM             | Redis             | TCP      | 6379 | Cache, rate limits, load-balancing state |

**No other communication is allowed** for this architecture (e.g. consumer apps must not call vLLM, PostgreSQL, or Redis).

---

## 3.2 Consumer Apps → LiteLLM

- **Direction:** Consumer app (RAG, Code Support, Translate, etc.) → LiteLLM.
- **Protocol:** HTTP (internal) or HTTPS (via Route).
- **Port:** 4000 (LiteLLM service).
- **Auth:** `Authorization: Bearer <virtual_key>` (or header set in LiteLLM config).
- **Endpoints used:**
  - `POST /v1/chat/completions` — chat.
  - `POST /v1/embeddings` — embeddings (if needed).
- **Payload:** OpenAI-compatible JSON (model, messages, etc.).
- **Example base URL (internal):** `http://litellm-service.llm-platform.svc.cluster.local:4000`
- **Example base URL (external):** `https://litellm-route-llm-platform.apps.<cluster>/`

---

## 3.3 LiteLLM → vLLM

- **Direction:** LiteLLM → each vLLM backend (multiple services).
- **Protocol:** HTTP (cluster-internal).
- **Port:** 8000 (per vLLM service).
- **Auth:** None (internal network).
- **Endpoints:** Same as OpenAI: `/v1/chat/completions`, `/v1/embeddings`.
- **Service DNS (examples):**
  - `http://vllm-llama-2-7b-service.llm-platform.svc.cluster.local:8000/v1`
  - `http://vllm-codellama-13b-service.llm-platform.svc.cluster.local:8000/v1`
  - etc.
- **Data:** Request body (messages, model, params); response (choices, usage).

---

## 3.4 LiteLLM → PostgreSQL

- **Direction:** LiteLLM → PostgreSQL only (no consumer app access).
- **Protocol:** TCP (TLS optional but recommended).
- **Port:** 5432.
- **Auth:** Username/password in `DATABASE_URL` (from secret).
- **Data:**
  - Virtual keys, teams, users.
  - Spend per key/user/team.
  - Schema managed by LiteLLM (Prisma migrations).
- **Connection:** Connection pooling; pool size per worker (see production guide).

---

## 3.5 LiteLLM → Redis

- **Direction:** LiteLLM → Redis only (no consumer app access).
- **Protocol:** TCP (optionally TLS).
- **Port:** 6379.
- **Auth:** Password (REDIS_PASSWORD from secret).
- **Data:**
  - **Cache:** Response cache (key → response, TTL).
  - **Rate limiting:** Counters per key/model (rpm/tpm).
  - **Load balancing:** Per-deployment state (e.g. load, health).
  - **Transaction buffer (optional):** Batched DB write queue (high RPS).
- **Config:** Use host + port + password (not redis_url) for production.

---

## 3.6 No Direct Communication (Explicit)

| Source           | Must NOT call |
|------------------|----------------|
| RAG app          | vLLM, PostgreSQL, Redis |
| Code Support app | vLLM, PostgreSQL, Redis |
| Translate app    | vLLM, PostgreSQL, Redis |
| vLLM backends    | LiteLLM, PostgreSQL, Redis (only respond to LiteLLM) |
| PostgreSQL       | Any app (only accepts from LiteLLM) |
| Redis            | Any app (only accepts from LiteLLM) |

This is enforced by **network policies** (see [05-network-and-security.md](./05-network-and-security.md)).

---

## 3.7 Sequence (Single Request)

1. User → Consumer App (e.g. RAG).
2. Consumer App → LiteLLM: `POST /v1/chat/completions` with API key.
3. LiteLLM → Redis: check cache; check rate limits.
4. LiteLLM → PostgreSQL: validate key, load key metadata (if needed).
5. LiteLLM: choose model and vLLM backend (using config + Redis state).
6. LiteLLM → vLLM: `POST /v1/chat/completions`.
7. vLLM → LiteLLM: completion response.
8. LiteLLM → Redis: update cache (on miss); update rate counters.
9. LiteLLM → PostgreSQL: update spend (or buffer in Redis if transaction buffer enabled).
10. LiteLLM → Consumer App: HTTP response (completion).
11. Consumer App → User: result.

All services involved in this path are listed in [02-services-inventory.md](./02-services-inventory.md).
