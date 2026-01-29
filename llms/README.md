# LLM-as-a-Service Architecture Documentation

This folder contains the complete architecture and deployment guide for building a centralized LLM-as-a-Service system using **LiteLLM** and **vLLM** on **OpenShift**.

## Contents

- **`llm-as-a-service-architecture.md`**: Main architecture document with comprehensive technical details
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

1. Read the main architecture document: `llm-as-a-service-architecture.md`
2. Review the architecture diagrams in `architecture-assets/`
3. Follow the deployment checklist in the architecture document

## Architecture Diagrams

- **High-level architecture**: System overview showing client services, LiteLLM, and vLLM backends
- **Component details**: How LiteLLM and vLLM integrate
- **OpenShift deployment**: Kubernetes resources and deployment structure

## Research Sources

This architecture is based on:

- **LiteLLM**: https://github.com/BerriAI/litellm
- **vLLM**: https://github.com/vllm-project/vllm
- **OpenShift**: Red Hat's Kubernetes distribution
- **PagedAttention**: Research paper on efficient KV cache management

## Questions?

Refer to the troubleshooting section in the main architecture document, or consult the official documentation for LiteLLM and vLLM.
