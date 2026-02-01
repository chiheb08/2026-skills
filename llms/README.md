# LLM-as-a-Service Architecture Documentation

This folder contains the complete architecture and deployment guide for building a centralized LLM-as-a-Service system using **LiteLLM** and **vLLM** on **OpenShift**.

## Contents

### Core Architecture Documents
- **`llm-as-a-service-architecture.md`**: Main architecture document with comprehensive technical details
- **`litellm-local-models-architecture.md`**: Detailed architecture guide for locally hosted models (vLLM only)
- **`architecture-diagrams.md`**: Interactive Mermaid diagrams for all architecture components
- **`production-best-practices.md`**: Best practices for a consistent, maintainable, long-lived platform (lifecycle, scaling, config, multi-app, observability, security, HA/DR, change management, runbooks, governance)

### Infrastructure Sizing
- **`infrastructure-sizing-700-1500-users.md`**: GPU (H200), CPU, and RAM requirements for 700–1500 users on-premise (vLLM, LiteLLM, PostgreSQL, Redis, OpenShift node layout)
- **`data-layer-resource-requirements.md`**: Resource parameters and values only for PostgreSQL and Redis (by user tier: 700, 1000, 1500 users) — copy-paste into YAML
- **`model-storage-and-replicas-explained.md`**: Where models are stored (PV/PVC), what “replicas” mean (one model in storage, multiple vLLM instances in memory), and how pods load models into GPU VRAM

### Configuration Files
- **`litellm-config-local-models.yaml`**: Production-ready configuration for locally hosted models
- **`litellm-production-configuration-guide.md`**: Complete production configuration guide for OpenShift & on-premise
- **`LOCAL-MODELS-CONFIG-README.md`**: Step-by-step guide for using the local models configuration

### Deep Dives
- **`redis-in-llm-apps-deep-dive.md`**: How Redis is used in modern LLM apps and specifically in LiteLLM (caching, rate limiting, load balancing, transaction buffer)
- **`litellm-data-layer-technical-challenges.md`**: Technical challenges of the data layer with LiteLLM (PostgreSQL, Redis, deadlocks, connection pools, migrations, encryption)
- **`litellm-postgres-teams-and-spend.md`**: Definitions of Teams and Spend in LiteLLM + PostgreSQL (what they are, how they are stored and used)
- **`litellm-teams-spend-architecture.md`**: Complete architecture diagrams and explanation of Teams & Spend tracking in on-premise infrastructure (with virtual budgets, chargeback, resource governance)

### Assets
- **`architecture-assets/`**: Architecture diagrams (PNG files)

## Quick Overview

The system consists of:

1. **LiteLLM**: Central API gateway that provides a unified interface to LLM providers
2. **vLLM**: High-performance inference engine running on GPU nodes
3. **Client Services**: RAG systems, code support tools, and other applications that consume LLM services

All components are deployed on **OpenShift** for scalability and management.

## Key Concepts

- **LiteLLM** acts as a proxy/router, making it easy to switch models or providers
- **vLLM** provides fast inference using PagedAttention and continuous batching
- **OpenShift** manages deployments, scaling, and networking

## Getting Started

### For Locally Hosted Models (Recommended)
1. Read **`litellm-local-models-architecture.md`** for complete architecture overview
2. Review **`architecture-diagrams.md`** for interactive visual diagrams
3. Use **`litellm-config-local-models.yaml`** as your configuration template
4. Follow **`LOCAL-MODELS-CONFIG-README.md`** for deployment steps

### For General Architecture
1. Read the main architecture document: `llm-as-a-service-architecture.md`
2. Review the architecture diagrams in `architecture-assets/`
3. Follow the deployment checklist in the architecture document

## Architecture Diagrams

### Interactive Diagrams (Mermaid)
- **`architecture-diagrams.md`**: Contains 12+ interactive Mermaid diagrams including:
  - High-level system architecture
  - Component interaction flows
  - Load balancing architecture
  - OpenShift deployment structure
  - Request flow diagrams
  - Failover and resilience
  - Network architecture
  - And more...

### Static Diagrams (PNG)
- **`architecture-assets/`**: Contains PNG diagrams:
  - High-level architecture
  - Component details
  - OpenShift deployment

## Research Sources

This architecture is based on:

- **LiteLLM**: https://github.com/BerriAI/litellm
- **vLLM**: https://github.com/vllm-project/vllm
- **OpenShift**: Red Hat's Kubernetes distribution
- **PagedAttention**: Research paper on efficient KV cache management

## Questions?

Refer to the troubleshooting section in the main architecture document, or consult the official documentation for LiteLLM and vLLM.
