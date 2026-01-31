# Central LLM Platform — On-Prem OpenShift Architecture

This folder contains the full architecture for a **central LiteLLM-based LLM platform** serving multiple consumer applications (RAG, code support, translate tool, etc.) on **on-premise OpenShift**, with **vLLM** for inference, **PostgreSQL** for persistence, and **Redis** for cache and coordination.

## Contents

| Document | Description |
|----------|-------------|
| [01-architecture-overview.md](./01-architecture-overview.md) | High-level architecture, service arrays, and design principles |
| [02-services-inventory.md](./02-services-inventory.md) | Complete list of all services with ports, dependencies, and config |
| [03-communication-matrix.md](./03-communication-matrix.md) | Who talks to whom: protocols, ports, and data flows |
| [04-openshift-deployment.md](./04-openshift-deployment.md) | Namespaces, deployments, services, routes, and storage |
| [05-network-and-security.md](./05-network-and-security.md) | Network policies, secrets, and security |
| [06-diagrams.md](./06-diagrams.md) | Mermaid diagrams for the full architecture |
| [services-inventory.yaml](./services-inventory.yaml) | Machine-readable service arrays and communication |

## Quick Reference

- **Central unit:** LiteLLM (API gateway, routing, rate limiting, keys).
- **Consumer apps:** RAG, code support, translate tool, and others — all call LiteLLM only.
- **Inference:** vLLM backends (local LLMs only).
- **Data:** PostgreSQL (keys, teams, spend); Redis (cache, rate limits, load-balancing state).
- **Platform:** OpenShift (on-prem); all workloads in-cluster.

## Related Repo Docs

- [LiteLLM production config](../litellm-production-configuration-guide.md)
- [Local models config](../litellm-config-local-models.yaml)
- [Redis deep dive](../redis-in-llm-apps-deep-dive.md)
