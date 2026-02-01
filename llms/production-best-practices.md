# Production Best Practices — LLM Platform (LiteLLM + vLLM on OpenShift)

This document describes best practices for building and operating a **consistent, maintainable, long-lived** LLM platform that serves **many applications** on-premise. It is based on patterns used in similar production systems (centralized inference gateways, multi-tenant API platforms, GPU clusters).

---

## Table of Contents

1. [Lifecycle Management](#1-lifecycle-management)
2. [Scaling and Capacity](#2-scaling-and-capacity)
3. [Configuration and Consistency](#3-configuration-and-consistency)
4. [Multi-Application and Multi-Tenancy](#4-multi-application-and-multi-tenancy)
5. [Observability and SLOs](#5-observability-and-slos)
6. [Security and Compliance](#6-security-and-compliance)
7. [High Availability and Disaster Recovery](#7-high-availability-and-disaster-recovery)
8. [Change Management and Rollouts](#8-change-management-and-rollouts)
9. [Documentation and Runbooks](#9-documentation-and-runbooks)
10. [Cost and Resource Governance](#10-cost-and-resource-governance)
11. [Testing and Validation](#11-testing-and-validation)
12. [Onboarding and Support](#12-onboarding-and-support)
13. [Checklist Summary](#13-checklist-summary)

---

## 1. Lifecycle Management

### 1.1 Model Lifecycle

- **Version models explicitly.**  
  Use a clear naming scheme: e.g. `llama-2-7b-v1`, `llama-2-7b-v2`, or `llama-2-7b-20260115`. Avoid “floating” names that silently point to new weights.

- **Store model artifacts in one place.**  
  Use a shared PV/PVC or a model registry (e.g. Hugging Face Hub, internal registry). Download/copy once; all vLLM replicas mount the same source. See [model-storage-and-replicas-explained.md](./model-storage-and-replicas-explained.md).

- **Document compatibility.**  
  Keep a matrix: model name/version ↔ vLLM version ↔ supported API (e.g. OpenAI-compatible fields). When you upgrade vLLM or a model, verify and document.

- **Deprecation policy.**  
  Define a timeline for old model versions (e.g. “v1 supported for 6 months after v2 GA”). Notify consumers (teams/apps) in advance; provide migration path (e.g. same API, new model name).

- **Retirement and cleanup.**  
  When a model version is retired, remove it from LiteLLM `model_list`, then remove weights from shared storage after a grace period. Archive config and metadata for audit.

### 1.2 Software Lifecycle (LiteLLM, vLLM, Dependencies)

- **Pin versions in production.**  
  Use explicit image tags (e.g. `litellm-database:1.2.3`, `vllm-openai:v0.6.1`) and dependency versions. Avoid `latest` in prod.

- **Upgrade path.**  
  Test upgrades in a staging environment that mirrors prod (same OpenShift version, same model set, similar load). Document upgrade steps and rollback procedure.

- **Compatibility matrix.**  
  Maintain a table: LiteLLM version ↔ vLLM version ↔ PostgreSQL/Redis versions. Upgrade in order (e.g. DB → Redis → vLLM → LiteLLM) when dependencies require it.

- **Security and CVEs.**  
  Subscribe to release notes and security advisories for LiteLLM, vLLM, base images, and OpenShift. Define SLAs for applying patches (e.g. critical within 7 days).

- **Long-term support (LTS) mindset.**  
  Prefer components with clear release and support policies. Plan one or two major upgrades per year; batch breaking changes and communicate them to consumers.

---

## 2. Scaling and Capacity

### 2.1 Horizontal Scaling

- **LiteLLM:**  
  Run at least 3 replicas for HA. Use HPA on CPU or RPS; set min replicas to 3 so you never drop below HA. Scale out before peak if you have predictable load.

- **vLLM:**  
  Add replicas per model when latency or queue depth grows. Use HPA on GPU utilization or custom metrics (e.g. request queue length). Prefer more replicas of smaller models over overloading few replicas.

- **Stateless design.**  
  LiteLLM and vLLM pods must be stateless. All shared state (keys, rate limits, spend) lives in PostgreSQL/Redis. This allows safe scaling and replacement of pods.

### 2.2 Vertical Scaling

- **When to scale up:**  
  Single-pod bottlenecks (e.g. one vLLM replica at 100% GPU utilization, or LiteLLM pod CPU saturated). Prefer horizontal first; vertical when you’re out of nodes or when a single replica is the natural unit (e.g. one 70B model per 2 GPUs).

- **Resource requests/limits.**  
  Set both. vLLM: request and limit 1 GPU per pod; memory request/limit aligned with model size and KV cache. LiteLLM: request/limit CPU and memory so the scheduler and QoS are predictable.

### 2.3 Capacity Planning

- **Forecast usage.**  
  Use historical spend, request counts, and token usage (from LiteLLM/PostgreSQL) to project growth. Revisit quarterly; plan GPU and node procurement ahead of need.

- **Headroom.**  
  Keep ~20–30% capacity headroom for peaks and growth. Document “max supported users” and “max RPS per model” for the current cluster size.

- **Sizing doc.**  
  Keep [infrastructure-sizing-700-1500-users.md](./infrastructure-sizing-700-1500-users.md) (or your equivalent) updated when you add models or change user counts.

---

## 3. Configuration and Consistency

### 3.1 Configuration as Code (GitOps)

- **Store all config in version control.**  
  LiteLLM `config.yaml`, OpenShift/Helm manifests, and env defaults in a repo. Use a GitOps tool (Argo CD, Flux, OpenShift GitOps) to apply to the cluster. No one-off `oc apply` or manual edits in prod.

- **Environments.**  
  Separate config per environment (e.g. `dev`, `staging`, `prod`). Same structure, different values (replicas, limits, feature flags). Promote changes through envs via PRs and pipelines.

- **Secrets.**  
  Do not commit secrets. Use a secret manager (e.g. Vault, OpenShift External Secrets) or sealed secrets. Reference secret names in Git; inject values at deploy time.

### 3.2 Naming and Structure

- **Consistent naming.**  
  Use a clear convention for models, services, and routes: e.g. `vllm-llama-2-7b-service`, `litellm-route`. Document the convention and stick to it so automation and runbooks stay simple.

- **Single source of truth.**  
  Model list, routing, and rate limits live in LiteLLM config. vLLM deployments and services align with that config (same model names and endpoints). Avoid duplicate lists (e.g. in both LiteLLM and a separate dashboard) that can drift.

- **Document config decisions.**  
  In the repo or wiki: why a model has a given RPM/TPM, why a route is named a certain way, and who owns which section of config.

---

## 4. Multi-Application and Multi-Tenancy

### 4.1 API Keys and Teams

- **One key per application (or per environment).**  
  E.g. RAG prod, RAG staging, code-support prod. Do not share keys across apps; this gives clear attribution and allows per-app rate limits and spend.

- **Use teams.**  
  Map apps to LiteLLM teams. Set team-level budgets and rate limits; use keys tied to teams. See [litellm-teams-spend-architecture.md](./litellm-teams-spend-architecture.md).

- **Naming keys and teams.**  
  Use names that identify the app and purpose: e.g. `rag-prod`, `code-support-staging`. Document key ↔ app ↔ team in a secure register or in team metadata.

### 4.2 Isolation and Fairness

- **Rate limits per key/team.**  
  Enforce RPM/TPM so one app cannot starve others. Set limits in LiteLLM config and optionally in Redis-backed rate limiting. Tune based on observed usage and SLOs.

- **Model access.**  
  Restrict which models each team/app can use via LiteLLM team or key config. Prevents accidental use of expensive or restricted models.

- **Budgets (on-prem).**  
  Use virtual budgets and spend tracking for chargeback/showback and to cap usage per team. See [litellm-teams-spend-architecture.md](./litellm-teams-spend-architecture.md).

### 4.3 Consistency Across Applications

- **Stable API contract.**  
  Expose a single OpenAI-compatible API via LiteLLM. All apps use the same base URL, auth (Bearer key), and request/response shape. Avoid app-specific endpoints or quirks; keep compatibility with standard clients.

- **Versioning.**  
  If you must change the API, use a version prefix (e.g. `/v1/`, `/v2/`) or headers. Deprecate old versions with notice; migrate apps gradually.

---

## 5. Observability and SLOs

### 5.1 Metrics

- **LiteLLM.**  
  Expose Prometheus metrics (request count, latency, errors by model and key). Scrape with OpenShift monitoring or Prometheus Operator. Key metrics: RPS, latency (p50, p95, p99), error rate, spend per key/team.

- **vLLM.**  
  Use vLLM’s Prometheus metrics: queue size, GPU utilization, tokens per second, batch size. Correlate with LiteLLM to see end-to-end latency and backlog.

- **PostgreSQL and Redis.**  
  Monitor connections, query latency, replication lag (if applicable), memory and disk. Alerts on connection exhaustion, high latency, or failures. See [litellm-data-layer-technical-challenges.md](./litellm-data-layer-technical-challenges.md).

### 5.2 Logging

- **Structured logs.**  
  JSON logs with consistent fields: timestamp, level, request_id, model, key_id (or hash), latency, status. Retain logs long enough for debugging and audit (e.g. 30–90 days). Avoid logging full prompts or PII in plain text; redact or hash if needed.

- **Central aggregation.**  
  Send logs to a central store (e.g. OpenShift Loki, Elasticsearch). Use the same request_id across LiteLLM and vLLM so you can trace a request end-to-end.

### 5.3 SLOs and Alerts

- **Define SLOs.**  
  E.g. “p99 latency &lt; 30 s for completions,” “availability 99.5%,” “error rate &lt; 0.1%.” Publish them to consumers (apps/teams).

- **Alert on SLO burn and failures.**  
  Alert when error rate or latency exceeds threshold, when LiteLLM/vLLM/PostgreSQL/Redis are down, or when queue depth is too high. Route alerts to an on-call rotation; keep alert volume low (avoid noise).

- **Dashboards.**  
  One dashboard per persona: platform (overall health, capacity), app owners (their key’s usage and errors), finance (spend by team). Use the same metric names and labels everywhere.

---

## 6. Security and Compliance

### 6.1 Secrets and Keys

- **No secrets in code or config repo.**  
  Use OpenShift Secrets or an external secret manager. Rotate `LITELLM_MASTER_KEY`, Redis and PostgreSQL credentials, and API keys on a schedule; document rotation and who can do it. Note: `LITELLM_SALT_KEY` cannot be rotated without breaking existing key hashes; protect it from the start. See [litellm-data-layer-technical-challenges.md](./litellm-data-layer-technical-challenges.md).

### 6.2 Access Control

- **Least privilege.**  
  Only platform/DevOps can change LiteLLM config, vLLM deployments, and data layer. App teams get virtual keys and read-only access to their usage/spend. Use RBAC and network policies so pods and users only reach what they need.

- **Network policies.**  
  Restrict traffic: consumers → LiteLLM only; LiteLLM → vLLM, PostgreSQL, Redis; no consumer → vLLM/DB/Redis. See [projects/05-network-and-security.md](./projects/05-network-and-security.md).

### 6.3 Data and Audit

- **Audit logging.**  
  Log key creation, key revocation, team changes, and config changes. Retain for compliance. Use PostgreSQL (or an audit log store) for durable audit records.

- **PII and prompts.**  
  Define policy: whether prompts/responses are logged, where, and for how long. Redact or restrict access; comply with internal and regulatory requirements.

---

## 7. High Availability and Disaster Recovery

### 7.1 Redundancy

- **LiteLLM:**  
  Minimum 3 replicas across nodes; prefer anti-affinity so no two replicas on the same node. Front with a load balancer or OpenShift Route.

- **vLLM:**  
  At least 2 replicas per model when HA is required; use pod anti-affinity so replicas are spread across nodes. For single-replica models (e.g. one 70B), document that model as best-effort HA or plan failover.

- **PostgreSQL:**  
  Run a primary + replicas (streaming replication). Failover via operator (e.g. Crunchy, CloudNativePG) or manual procedure. Back up regularly (WAL archiving, base backups).

- **Redis:**  
  Use Sentinel or Redis Cluster for HA. See [redis-in-llm-apps-deep-dive.md](./redis-in-llm-apps-deep-dive.md).

### 7.2 Disaster Recovery

- **RTO/RPO.**  
  Define recovery time objective (RTO) and recovery point objective (RPO). E.g. “RTO 4 h, RPO 1 h.” Design backups and failover to meet them.

- **Backups.**  
  PostgreSQL: continuous WAL archiving and base backups; test restore regularly. Redis: persistence (RDB/AOF) and backup if needed for replay. Config and secrets: stored in Git and secret manager; recoverable. Model weights: large; back up from shared storage or re-download from registry.

- **DR drills.**  
  Periodically run failover and restore in a non-prod environment. Document steps and update runbooks from findings.

---

## 8. Change Management and Rollouts

### 8.1 Change Process

- **All prod changes via pipeline and review.**  
  Config and app changes go through PR, review, and CI. Deploy to staging first; then promote to prod via GitOps or release process. No ad-hoc edits in prod.

- **Change calendar.**  
  Schedule major changes (LiteLLM/vLLM upgrades, model additions/removals, DB migrations) in advance. Notify consumers; avoid high-traffic periods.

### 8.2 Safe Rollouts

- **Canary or staged rollout.**  
  For LiteLLM or vLLM image upgrades: roll out to a subset of replicas, watch metrics and errors, then roll out to the rest. Use deployment strategies (rolling update, canary) and readiness/liveness probes.

- **Model rollouts.**  
  Add a new model version as a new entry in `model_list` (e.g. `llama-2-7b-v2`). Let consumers migrate gradually; deprecate old version on a defined timeline.

- **Rollback.**  
  Keep previous image tags and config versions available. Document rollback steps (e.g. revert Git commit, or redeploy previous manifest). Test rollback in staging.

---

## 9. Documentation and Runbooks

### 9.1 Living Documentation

- **Architecture.**  
  Keep architecture docs (e.g. [projects/01-architecture-overview.md](./projects/01-architecture-overview.md), [litellm-local-models-architecture.md](./litellm-local-models-architecture.md)) up to date when you add components or change flows. One source of truth; link from README.

- **Operational runbooks.**  
  For every alert and every critical procedure: “When X happens, do Y.” Include: how to scale LiteLLM/vLLM, how to restart a stuck vLLM pod, how to fail over PostgreSQL, how to rotate secrets, how to add a new model or key. Keep runbooks in the same repo or wiki; review quarterly.

### 9.2 Onboarding and Escalation

- **Onboarding new apps.**  
  Document: how to get an API key, base URL, rate limits, supported models, and example requests. Provide a small test script or Postman collection. Link to SLOs and status page if you have one.

- **Escalation.**  
  Define support tiers: L1 (app team), L2 (platform team), L3 (vendor or specialist). Publish contact and escalation path; include in runbooks.

---

## 10. Cost and Resource Governance

### 10.1 Budgets and Chargeback

- **Virtual budgets (on-prem).**  
  Use LiteLLM teams and spend tracking for internal chargeback/showback. Set monthly (or weekly) budgets per team; enforce via LiteLLM. See [litellm-teams-spend-architecture.md](./litellm-teams-spend-architecture.md).

- **Visibility.**  
  Dashboards and reports per team/app: spend, token usage, top models. Share with cost owners; review in capacity and budget meetings.

### 10.2 Right-Sizing and Cleanup

- **Idle resources.**  
  Scale down or remove unused model replicas (e.g. a model no app uses). Monitor “zero traffic” models and decommission after a grace period.

- **Orphaned keys.**  
  Periodically list keys and revoke those tied to decommissioned apps or expired projects. Reduces abuse surface and keeps spend data clean.

---

## 11. Testing and Validation

### 11.1 Pre-Production

- **Staging environment.**  
  Mirror prod (same OpenShift version, same LiteLLM/vLLM/DB/Redis topology, same config shape). Use smaller replicas or fewer nodes if needed; load test before major releases.

- **Smoke tests.**  
  After deploy or config change: call LiteLLM health endpoint, send a minimal completion request per model, check that spend is recorded. Automate in CI or post-deploy job.

### 11.2 Load and Compatibility

- **Load tests.**  
  Periodically run load tests (e.g. Locust, k6) against staging or prod to validate capacity and SLOs. See LiteLLM’s [load test docs](https://docs.litellm.ai/docs/load_test_advanced). Correlate with GPU and DB metrics.

- **Compatibility.**  
  When upgrading LiteLLM or vLLM, run a compatibility suite: all consumer apps (or representative clients) against staging with the new versions. Catch breaking API or behavior changes before prod.

---

## 12. Onboarding and Support

### 12.1 Consumer Experience

- **Single entry point.**  
  All apps use one LiteLLM base URL and one auth model (Bearer key). Document base URL, how to get a key, and link to status/docs.

- **Stability.**  
  Avoid breaking changes to the public API. Version the API if you must change; communicate deprecations and migration paths. A long-lived platform earns trust by being predictable.

### 12.2 Feedback and Roadmap

- **Usage and pain points.**  
  Collect feedback from app teams: missing models, rate limit issues, latency complaints, feature requests. Use this for capacity planning and roadmap.

- **Roadmap.**  
  Publish a short-term roadmap (e.g. next quarter): new models, upgrades, deprecations. Align with capacity and lifecycle plans.

---

## 13. Checklist Summary

Use this as a quick checklist; details are in the sections above.

| Area | Practices |
|------|-----------|
| **Lifecycle** | Model versioning; deprecation policy; pinned software versions; upgrade path and compatibility matrix; security patching. |
| **Scaling** | LiteLLM ≥3 replicas + HPA; vLLM replicas + HPA; stateless design; 20–30% headroom; capacity planning. |
| **Config** | GitOps; config in Git; secrets out of repo; consistent naming; single source of truth. |
| **Multi-app** | One key per app; teams and budgets; rate limits and model access; stable API contract. |
| **Observability** | Metrics (LiteLLM, vLLM, DB, Redis); structured logs; SLOs and alerts; dashboards. |
| **Security** | No secrets in code; rotation; least privilege; network policies; audit logging. |
| **HA/DR** | Redundant LiteLLM, vLLM, PostgreSQL, Redis; backups; RTO/RPO; DR drills. |
| **Changes** | All changes via pipeline and review; canary/staged rollouts; rollback procedure. |
| **Docs** | Up-to-date architecture and runbooks; onboarding and escalation. |
| **Governance** | Budgets and chargeback; right-sizing; key cleanup. |
| **Testing** | Staging; smoke tests; load tests; compatibility tests on upgrades. |
| **Support** | Single entry point; stability; feedback and roadmap. |

---

## References

- [litellm-production-configuration-guide.md](./litellm-production-configuration-guide.md)
- [litellm-data-layer-technical-challenges.md](./litellm-data-layer-technical-challenges.md)
- [litellm-teams-spend-architecture.md](./litellm-teams-spend-architecture.md)
- [infrastructure-sizing-700-1500-users.md](./infrastructure-sizing-700-1500-users.md)
- [model-storage-and-replicas-explained.md](./model-storage-and-replicas-explained.md)
- [projects/](./projects/) — architecture, deployment, network, security
