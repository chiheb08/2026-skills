# LiteLLM Production Configuration Guide for OpenShift & On-Premise Datacenter

## Overview

This document provides a comprehensive guide for configuring LiteLLM Proxy in a production environment on **OpenShift** and **on-premise datacenter**. It covers all required configuration data, environment variables, secrets, and best practices based on the official LiteLLM documentation.

---

## Table of Contents

1. [Required Environment Variables](#required-environment-variables)
2. [Configuration File (config.yaml)](#configuration-file-configyaml)
3. [Database Configuration](#database-configuration)
4. [Redis Configuration](#redis-configuration)
5. [Security & Secrets Management](#security--secrets-management)
6. [OpenShift-Specific Configuration](#openshift-specific-configuration)
7. [Production Best Practices](#production-best-practices)
8. [Complete Configuration Example](#complete-configuration-example)

---

## Required Environment Variables

### Core Required Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `LITELLM_MASTER_KEY` | Admin key for proxy (must start with `sk-`) | `sk-1234...` | ✅ Yes (if using DB) |
| `LITELLM_SALT_KEY` | Encryption key for API keys in DB (cannot change after setup) | `sk-abc123...` | ✅ Yes (if using DB) |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/dbname` | ✅ Yes (for virtual keys) |
| `LITELLM_MODE` | Set to `PRODUCTION` to disable `.env` loading | `PRODUCTION` | ✅ Yes (production) |

### Optional Production Variables

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `LITELLM_LOG` | Log level | `ERROR` | `INFO` |
| `SLACK_WEBHOOK_URL` | Slack webhook for alerts | `https://hooks.slack.com/...` | - |
| `DISABLE_SCHEMA_UPDATE` | Disable DB migrations in pods | `true` | `false` |
| `USE_PRISMA_MIGRATE` | Use `prisma migrate deploy` | `True` | `false` |
| `LITELLM_MIGRATION_DIR` | Directory for migration files | `/tmp/migrations` | - |
| `SEPARATE_HEALTH_APP` | Enable separate health check app | `1` | `0` |
| `SEPARATE_HEALTH_PORT` | Port for health check app | `8001` | `4001` |
| `SUPERVISORD_STOPWAITSECS` | Graceful shutdown timeout | `3600` | `3600` |
| `MAX_REQUESTS_BEFORE_RESTART` | Restart workers after N requests | `10000` | - |
| `KEEPALIVE_TIMEOUT` | Keepalive timeout in seconds | `75` | `5` |
| `LITELLM_LOCAL_MODEL_COST_MAP` | Use local model prices | `True` | `false` |
| `NO_DOCS` | Disable Swagger UI | `True` | `false` |
| `NO_REDOC` | Disable Redoc | `True` | `false` |
| `CONFIG_FILE_PATH` | Path to config.yaml | `/app/config.yaml` | - |

### Redis Environment Variables (if using Redis)

| Variable | Description | Example |
|----------|-------------|---------|
| `REDIS_HOST` | Redis hostname | `redis-service.redis.svc.cluster.local` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_PASSWORD` | Redis password | `your-redis-password` |

### LLM Provider API Keys (Model-Specific)

These should be stored as **OpenShift Secrets** and referenced in `config.yaml`:

| Variable | Provider | Example |
|----------|----------|---------|
| `OPENAI_API_KEY` | OpenAI | `sk-...` |
| `AZURE_API_KEY` | Azure OpenAI | `...` |
| `AZURE_API_BASE` | Azure OpenAI | `https://...openai.azure.com/` |
| `AZURE_API_VERSION` | Azure OpenAI | `2025-01-01-preview` |
| `ANTHROPIC_API_KEY` | Anthropic | `sk-ant-...` |
| `HUGGINGFACE_API_KEY` | HuggingFace | `hf_...` |
| `NVIDIA_NIM_API_KEY` | NVIDIA NIM | `...` |
| `NVIDIA_NIM_API_BASE` | NVIDIA NIM | `https://...` |

---

## Configuration File (config.yaml)

### Production-Ready config.yaml Structure

```yaml
# ============================================
# LiteLLM Production Configuration
# For OpenShift + On-Premise Datacenter
# ============================================

model_list:
  # Example: Azure OpenAI Model
  - model_name: gpt-4o-production
    litellm_params:
      model: azure/gpt-4o
      api_base: os.environ/AZURE_API_BASE
      api_key: os.environ/AZURE_API_KEY
      api_version: "2025-01-01-preview"
    rpm: 200  # Requests per minute limit
    tpm: 100000  # Tokens per minute limit

  # Example: Multiple deployments for load balancing
  - model_name: gpt-4o-production
    litellm_params:
      model: azure/gpt-4o
      api_base: os.environ/AZURE_API_BASE_EU
      api_key: os.environ/AZURE_API_KEY_EU
      api_version: "2025-01-01-preview"
    rpm: 200
    tpm: 100000

  # Example: Local vLLM Backend
  - model_name: llama-2-7b
    litellm_params:
      model: openai/llama-2-7b
      api_base: http://vllm-backend-llama-2-7b.llm-service.svc.cluster.local:8000/v1
      api_key: dummy-key
    rpm: 600
    tpm: 50000

  # Example: Anthropic Claude
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    rpm: 100
    tpm: 80000

# Router Settings (for load balancing across multiple instances)
router_settings:
  routing_strategy: simple-shuffle  # Options: simple-shuffle, least-busy, latency-based-routing, cost-based-routing
  num_retries: 2
  timeout: 30
  # Redis configuration (REQUIRED for multi-instance deployments)
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD
  # DO NOT use redis_url - it's 80 RPS slower

# LiteLLM Module Settings
litellm_settings:
  # Request handling
  request_timeout: 600  # 10 minutes max request time
  num_retries: 3
  set_verbose: False  # Disable debug logging in production
  json_logs: true  # JSON format for log aggregation
  
  # Caching (if using Redis)
  cache: true
  cache_params:
    type: redis
    host: os.environ/REDIS_HOST
    port: os.environ/REDIS_PORT
    password: os.environ/REDIS_PASSWORD
  
  # Fallback configuration
  fallbacks:
    - {"gpt-4o-production": ["claude-3-5-sonnet"]}
  
  context_window_fallbacks:
    - {"gpt-4o-production": ["llama-2-7b"]}
  
  allowed_fails: 3  # Cooldown model after 3 failures in 1 minute
  
  # Drop unsupported parameters
  drop_params: True

# General Settings
general_settings:
  # Master key (must start with 'sk-')
  master_key: os.environ/LITELLM_MASTER_KEY
  
  # Database connection
  database_url: os.environ/DATABASE_URL
  
  # Connection pool settings
  database_connection_pool_limit: 10  # Per worker process
  # Formula: MAX_DB_CONNECTIONS / (instances × workers)
  # Example: 100 max connections, 3 instances, 4 workers each
  # = 100 / (3 × 4) = 8.33 → use 8 or 10
  
  database_connection_timeout: 60  # 60 seconds timeout
  
  # Alerting
  alerting: ["slack"]  # Requires SLACK_WEBHOOK_URL env var
  
  # Batch write spend updates
  proxy_batch_write_at: 60  # Write every 60 seconds
  
  # Production optimizations
  disable_error_logs: True  # Don't write LLM exceptions to DB
  allow_requests_on_db_unavailable: True  # Only for VPC deployments
  
  # Optional: Custom key header name
  # litellm_key_header_name: "X-Litellm-Key"
```

### Key Configuration Sections Explained

#### 1. model_list
- **model_name**: User-facing name for the model
- **litellm_params.model**: Actual model identifier (provider/model)
- **rpm/tpm**: Rate limits per deployment
- **api_key**: Use `os.environ/VAR_NAME` to load from environment

#### 2. router_settings
- **routing_strategy**: `simple-shuffle` recommended for production
- **redis_***: Required for multi-instance load balancing
- **num_retries**: Retry failed requests
- **timeout**: Request timeout in seconds

#### 3. litellm_settings
- **request_timeout**: Maximum request duration
- **set_verbose**: Set to `False` in production
- **json_logs**: Enable JSON logging for log aggregation
- **cache**: Enable Redis caching for responses

#### 4. general_settings
- **master_key**: Admin key for proxy management
- **database_url**: PostgreSQL connection string
- **database_connection_pool_limit**: Calculate based on your setup
- **disable_error_logs**: Reduce DB writes
- **allow_requests_on_db_unavailable**: For VPC deployments only

---

## Database Configuration

### PostgreSQL Requirements

**Minimum Specifications:**
- PostgreSQL 12+ (recommended: 14+)
- Connection pool: Calculate based on instances × workers
- SSL/TLS: Recommended for production

**Connection String Format:**
```
postgresql://[user]:[password]@[host]:[port]/[database]?sslmode=require
```

**Example for OpenShift:**
```
postgresql://litellm_user:password@postgres-service.database.svc.cluster.local:5432/litellm_db?sslmode=require
```

### Database Connection Pool Calculation

**Formula:**
```
database_connection_pool_limit = MAX_DB_CONNECTIONS / (instances × workers_per_instance)
```

**Example:**
- Database max connections: 100
- LiteLLM instances: 3
- Workers per instance: 4 (set via `--num_workers`)
- Calculation: 100 / (3 × 4) = 8.33
- **Set to: 8 or 10** (leave buffer)

### Database Migrations

**For Production (Helm PreSync Hook):**
```yaml
# In Helm chart, use PreSync hook for migrations
# Set in LiteLLM pods:
env:
  - name: DISABLE_SCHEMA_UPDATE
    value: "true"
```

**For Manual Migrations:**
```bash
export USE_PRISMA_MIGRATE=True
litellm --config config.yaml
```

**For Read-Only File Systems:**
```bash
export LITELLM_MIGRATION_DIR=/tmp/migrations
```

---

## Redis Configuration

### Redis Requirements

**Minimum Version:** Redis 7.0+

**Why Redis is Required:**
- Load balancing across multiple LiteLLM instances
- Shared rate limiting (rpm/tpm) across instances
- Caching responses
- Transaction buffering (prevents DB deadlocks at high traffic)

### Redis Configuration in config.yaml

```yaml
router_settings:
  # Use host, port, password - NOT redis_url (80 RPS slower)
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD

litellm_settings:
  cache: true
  cache_params:
    type: redis
    host: os.environ/REDIS_HOST
    port: os.environ/REDIS_PORT
    password: os.environ/REDIS_PASSWORD
```

### High Traffic Deployments (1000+ RPS)

**Additional Redis Configuration:**
```yaml
general_settings:
  use_redis_transaction_buffer: true  # Prevents DB deadlocks
```

---

## Security & Secrets Management

### OpenShift Secrets

**Create secrets for sensitive data:**

```bash
# Create secret for LiteLLM master key and salt
oc create secret generic litellm-secrets \
  --from-literal=LITELLM_MASTER_KEY='sk-...' \
  --from-literal=LITELLM_SALT_KEY='sk-...' \
  --from-literal=DATABASE_URL='postgresql://...' \
  -n llm-service

# Create secret for LLM provider API keys
oc create secret generic llm-provider-keys \
  --from-literal=AZURE_API_KEY='...' \
  --from-literal=AZURE_API_BASE='https://...' \
  --from-literal=ANTHROPIC_API_KEY='sk-ant-...' \
  --from-literal=OPENAI_API_KEY='sk-...' \
  -n llm-service

# Create secret for Redis
oc create secret generic redis-secrets \
  --from-literal=REDIS_HOST='redis-service.redis.svc.cluster.local' \
  --from-literal=REDIS_PORT='6379' \
  --from-literal=REDIS_PASSWORD='...' \
  -n llm-service
```

### Secret Rotation

**LiteLLM Salt Key:**
- ⚠️ **CANNOT be changed** after adding models
- Used to encrypt/decrypt API keys in database
- Generate using: https://1password.com/password-generator/
- Store securely in OpenShift Secrets

**Master Key:**
- Can be rotated
- Must start with `sk-`
- Used for admin operations (key generation, etc.)

### Network Security

**Network Policies (OpenShift):**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: litellm-network-policy
  namespace: llm-service
spec:
  podSelector:
    matchLabels:
      app: litellm
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: allowed-namespaces
      ports:
        - protocol: TCP
          port: 4000
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: database
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - namespaceSelector:
            matchLabels:
              name: redis
      ports:
        - protocol: TCP
          port: 6379
```

---

## OpenShift-Specific Configuration

### Deployment Configuration

**Recommended Deployment Spec:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-proxy
  namespace: llm-service
spec:
  replicas: 3  # Horizontal scaling
  selector:
    matchLabels:
      app: litellm
  template:
    metadata:
      labels:
        app: litellm
    spec:
      containers:
      - name: litellm
        image: docker.litellm.ai/berriai/litellm-database:main-stable
        # Use version tags, not 'latest' or 'stable'
        imagePullPolicy: Always
        ports:
        - containerPort: 4000
          name: http
        args:
          - "--port"
          - "4000"
          - "--config"
          - "/app/config.yaml"
          - "--num_workers"
          - "$(nproc)"  # Match workers to CPU count
          - "--max_requests_before_restart"
          - "10000"  # Optional: restart workers after 10k requests
          - "--run_gunicorn"  # More stable worker recycling
        env:
        # Core configuration
        - name: LITELLM_MODE
          value: "PRODUCTION"
        - name: LITELLM_LOG
          value: "ERROR"
        - name: DISABLE_SCHEMA_UPDATE
          value: "true"  # Use Helm PreSync hook for migrations
        - name: SEPARATE_HEALTH_APP
          value: "1"  # Separate health check app
        - name: SEPARATE_HEALTH_PORT
          value: "8001"
        - name: SUPERVISORD_STOPWAITSECS
          value: "3600"
        # Load from secrets
        - name: LITELLM_MASTER_KEY
          valueFrom:
            secretKeyRef:
              name: litellm-secrets
              key: LITELLM_MASTER_KEY
        - name: LITELLM_SALT_KEY
          valueFrom:
            secretKeyRef:
              name: litellm-secrets
              key: LITELLM_SALT_KEY
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: litellm-secrets
              key: DATABASE_URL
        - name: REDIS_HOST
          valueFrom:
            secretKeyRef:
              name: redis-secrets
              key: REDIS_HOST
        - name: REDIS_PORT
          valueFrom:
            secretKeyRef:
              name: redis-secrets
              key: REDIS_PORT
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-secrets
              key: REDIS_PASSWORD
        envFrom:
        - secretRef:
            name: llm-provider-keys
        resources:
          requests:
            cpu: "2"
            memory: 4Gi
          limits:
            cpu: "4"
            memory: 8Gi
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health/liveliness
            port: 8001  # Separate health port
          initialDelaySeconds: 120
          periodSeconds: 15
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 8001  # Separate health port
          initialDelaySeconds: 120
          periodSeconds: 15
          timeoutSeconds: 10
          failureThreshold: 3
      volumes:
      - name: config
        configMap:
          name: litellm-config
```

### ConfigMap for config.yaml

```bash
# Create ConfigMap from config file
oc create configmap litellm-config \
  --from-file=config.yaml=./config.yaml \
  -n llm-service
```

### Service Configuration

```yaml
apiVersion: v1
kind: Service
metadata:
  name: litellm-service
  namespace: llm-service
spec:
  selector:
    app: litellm
  ports:
  - port: 4000
    targetPort: 4000
    protocol: TCP
    name: http
  type: ClusterIP
```

### Route Configuration (External Access)

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: litellm-route
  namespace: llm-service
spec:
  to:
    kind: Service
    name: litellm-service
  port:
    targetPort: 4000
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
```

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: litellm-hpa
  namespace: llm-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: litellm-proxy
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Production Best Practices

### 1. Machine Specifications

**Minimum Requirements:**
- **CPU:** 4 vCPU
- **Memory:** 8 GB RAM

**Recommended:**
- **CPU:** 4-8 vCPU per pod
- **Memory:** 8-16 GB per pod

### 2. Worker Configuration

**Match workers to CPU count:**
```bash
--num_workers $(nproc)
```

**For worker recycling (memory leak mitigation):**
```bash
--max_requests_before_restart 10000
--run_gunicorn  # More stable than Uvicorn for recycling
```

### 3. Logging Configuration

**Production Log Settings:**
```bash
export LITELLM_LOG="ERROR"  # Only errors
export LITELLM_MODE="PRODUCTION"  # Disable .env loading
```

**In config.yaml:**
```yaml
litellm_settings:
  set_verbose: False
  json_logs: true  # For log aggregation systems
```

### 4. Alerting Setup

**Slack Webhook:**
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

**In config.yaml:**
```yaml
general_settings:
  alerting: ["slack"]
```

**Alerts for:**
- LLM exceptions
- Budget alerts
- Slow LLM responses

### 5. Database Optimization

**Connection Pool:**
- Calculate: `MAX_DB_CONNECTIONS / (instances × workers)`
- Set `database_connection_pool_limit` accordingly

**High Traffic (1000+ RPS):**
```yaml
general_settings:
  use_redis_transaction_buffer: true  # Prevents DB deadlocks
```

### 6. VPC/On-Premise Considerations

**For VPC deployments (no public internet):**
```yaml
general_settings:
  allow_requests_on_db_unavailable: True  # Graceful degradation
```

**Expected Behavior:**
- ✅ Requests continue if DB is temporarily unavailable
- ✅ Pods start even if DB is down
- ✅ Health checks return 200 OK
- ❌ Budget/model errors still block requests

### 7. SSL/TLS Configuration

**For on-premise with custom certificates:**
```bash
litellm --config config.yaml \
  --ssl_keyfile_path /path/to/keyfile.key \
  --ssl_certfile_path /path/to/certfile.crt
```

### 8. Disable Documentation Endpoints

**For production:**
```bash
export NO_DOCS="True"  # Disable Swagger UI
export NO_REDOC="True"  # Disable Redoc
```

---

## Complete Configuration Example

### Full Production config.yaml

```yaml
# ============================================
# LiteLLM Production Configuration
# OpenShift + On-Premise Datacenter
# ============================================

model_list:
  # Production Azure OpenAI Model
  - model_name: gpt-4o-prod
    litellm_params:
      model: azure/gpt-4o
      api_base: os.environ/AZURE_API_BASE
      api_key: os.environ/AZURE_API_KEY
      api_version: "2025-01-01-preview"
    rpm: 200
    tpm: 100000
    model_info:
      supported_environments: ["production"]

  # EU Region Deployment (Load Balancing)
  - model_name: gpt-4o-prod
    litellm_params:
      model: azure/gpt-4o
      api_base: os.environ/AZURE_API_BASE_EU
      api_key: os.environ/AZURE_API_KEY_EU
      api_version: "2025-01-01-preview"
    rpm: 200
    tpm: 100000

  # Local vLLM Backend
  - model_name: llama-2-7b
    litellm_params:
      model: openai/llama-2-7b
      api_base: http://vllm-backend-llama-2-7b.llm-service.svc.cluster.local:8000/v1
      api_key: dummy-key
    rpm: 600
    tpm: 50000

  # Anthropic Claude
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    rpm: 100
    tpm: 80000

# Router Settings
router_settings:
  routing_strategy: simple-shuffle  # Best performance
  num_retries: 2
  timeout: 30
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD

# LiteLLM Settings
litellm_settings:
  request_timeout: 600
  num_retries: 3
  set_verbose: False
  json_logs: true
  drop_params: True
  
  # Caching
  cache: true
  cache_params:
    type: redis
    host: os.environ/REDIS_HOST
    port: os.environ/REDIS_PORT
    password: os.environ/REDIS_PASSWORD
  
  # Fallbacks
  fallbacks:
    - {"gpt-4o-prod": ["claude-3-5-sonnet"]}
  context_window_fallbacks:
    - {"gpt-4o-prod": ["llama-2-7b"]}
  allowed_fails: 3

# General Settings
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  database_connection_pool_limit: 10
  database_connection_timeout: 60
  alerting: ["slack"]
  proxy_batch_write_at: 60
  disable_error_logs: True
  allow_requests_on_db_unavailable: True  # For VPC
  use_redis_transaction_buffer: true  # High traffic
```

### Complete Environment Variables List

```bash
# Core Configuration
export LITELLM_MODE="PRODUCTION"
export LITELLM_LOG="ERROR"
export LITELLM_MASTER_KEY="sk-..."  # From secret
export LITELLM_SALT_KEY="sk-..."  # From secret (cannot change)

# Database
export DATABASE_URL="postgresql://user:pass@host:5432/dbname?sslmode=require"
export DISABLE_SCHEMA_UPDATE="true"  # Use Helm PreSync hook
export USE_PRISMA_MIGRATE="True"
export LITELLM_MIGRATION_DIR="/tmp/migrations"  # If read-only filesystem

# Redis
export REDIS_HOST="redis-service.redis.svc.cluster.local"
export REDIS_PORT="6379"
export REDIS_PASSWORD="..."  # From secret

# Health Checks
export SEPARATE_HEALTH_APP="1"
export SEPARATE_HEALTH_PORT="8001"
export SUPERVISORD_STOPWAITSECS="3600"

# Performance
export MAX_REQUESTS_BEFORE_RESTART="10000"
export KEEPALIVE_TIMEOUT="75"

# Features
export LITELLM_LOCAL_MODEL_COST_MAP="True"  # Disable live price fetching
export NO_DOCS="True"  # Disable Swagger
export NO_REDOC="True"  # Disable Redoc

# Alerting
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."

# LLM Provider Keys (from secrets)
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://...openai.azure.com/"
export AZURE_API_VERSION="2025-01-01-preview"
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

---

## Configuration Checklist

### Pre-Deployment

- [ ] Generate `LITELLM_MASTER_KEY` (starts with `sk-`)
- [ ] Generate `LITELLM_SALT_KEY` (use password generator, cannot change later)
- [ ] Set up PostgreSQL database (12+)
- [ ] Set up Redis (7.0+)
- [ ] Create OpenShift Secrets for all sensitive data
- [ ] Create ConfigMap for `config.yaml`
- [ ] Calculate database connection pool limit
- [ ] Configure network policies
- [ ] Set up monitoring/logging

### Deployment

- [ ] Deploy LiteLLM with production environment variables
- [ ] Configure health checks (separate health app recommended)
- [ ] Set up OpenShift Route for external access
- [ ] Configure HPA for auto-scaling
- [ ] Test database connectivity
- [ ] Test Redis connectivity
- [ ] Verify model endpoints are accessible

### Post-Deployment

- [ ] Generate virtual keys via `/key/generate` endpoint
- [ ] Test model routing and load balancing
- [ ] Verify fallback mechanisms
- [ ] Test rate limiting
- [ ] Monitor logs for errors
- [ ] Set up alerting (Slack webhook)
- [ ] Load test the deployment
- [ ] Document API endpoints for clients

---

## Troubleshooting

### Common Issues

**1. Database Connection Errors**
- Check `DATABASE_URL` format
- Verify network policies allow DB access
- Check connection pool limit calculation
- Ensure SSL mode matches DB configuration

**2. Redis Connection Errors**
- Verify `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- Check network policies
- Ensure Redis version is 7.0+

**3. High Memory Usage**
- Enable `--max_requests_before_restart`
- Use `--run_gunicorn` for stable recycling
- Monitor worker memory per instance

**4. Slow Performance**
- Check Redis configuration (use host/port/password, not redis_url)
- Verify routing strategy (`simple-shuffle` recommended)
- Check database connection pool limits
- Monitor Redis and DB latency

**5. Health Check Failures**
- Enable `SEPARATE_HEALTH_APP=1`
- Use separate health port
- Verify health endpoints are accessible

---

## References

- [LiteLLM Official Documentation](https://docs.litellm.ai)
- [LiteLLM Production Best Practices](https://docs.litellm.ai/docs/proxy/prod)
- [LiteLLM Configuration Guide](https://docs.litellm.ai/docs/proxy/configs)
- [LiteLLM Deployment Guide](https://docs.litellm.ai/docs/proxy/deploy)
- [LiteLLM GitHub Repository](https://github.com/BerriAI/litellm)

---

## Summary

This guide provides all the configuration data needed for deploying LiteLLM in production on OpenShift and on-premise datacenter environments. Key takeaways:

1. **Required:** `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `DATABASE_URL`
2. **Recommended:** Redis for multi-instance deployments
3. **Production:** Set `LITELLM_MODE=PRODUCTION`, `LITELLM_LOG=ERROR`
4. **Security:** Use OpenShift Secrets for all sensitive data
5. **Performance:** Match workers to CPU, use `simple-shuffle` routing
6. **Reliability:** Enable separate health app, configure proper timeouts

For questions or issues, refer to the official LiteLLM documentation or GitHub issues.
