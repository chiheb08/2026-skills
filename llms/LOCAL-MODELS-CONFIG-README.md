# LiteLLM Configuration for Locally Hosted Models

## Overview

This configuration file (`litellm-config-local-models.yaml`) is optimized for **production deployments** where **all models are hosted locally** in your OpenShift cluster using **vLLM** backends. No external LLM providers are used.

## Key Features

✅ **Local-only models**: All models run on vLLM backends in your cluster  
✅ **Load balancing**: Multiple instances per model for high availability  
✅ **Production-optimized**: Redis caching, connection pooling, error handling  
✅ **OpenShift-ready**: Uses Kubernetes service DNS names  
✅ **No external dependencies**: No API keys for external providers needed  

## Architecture

```
Client Services
    ↓
LiteLLM Proxy (this config)
    ↓
vLLM Backends (local models)
    ├── llama-2-7b (2 instances)
    ├── codellama-13b (2 instances)
    ├── mistral-7b (2 instances)
    └── llama-2-70b (1 instance)
```

## Configuration Structure

### Model Configuration

Each model entry includes:

- **model_name**: User-facing name (what clients use)
- **litellm_params.model**: Must use `openai/` prefix for vLLM compatibility
- **litellm_params.api_base**: Kubernetes service DNS name
- **rpm/tpm**: Rate limits (requests/tokens per minute)
- **model_info**: Metadata about the model

### Example Model Entry

```yaml
- model_name: llama-2-7b
  litellm_params:
    model: openai/llama-2-7b  # 'openai/' prefix required
    api_base: http://vllm-llama-2-7b-service.llm-service.svc.cluster.local:8000/v1
    api_key: dummy-key  # vLLM doesn't require real keys
  rpm: 600
  tpm: 50000
```

## Prerequisites

### 1. vLLM Backends Running

Ensure your vLLM backends are deployed and accessible via Kubernetes services:

```yaml
# Example vLLM Service
apiVersion: v1
kind: Service
metadata:
  name: vllm-llama-2-7b-service
  namespace: llm-service
spec:
  selector:
    app: vllm
    model: llama-2-7b
  ports:
  - port: 8000
    targetPort: 8000
```

### 2. Required Services

- **PostgreSQL**: For virtual keys and spend tracking
- **Redis**: For caching and multi-instance load balancing
- **vLLM Services**: One service per model/instance

### 3. OpenShift Secrets

Create secrets for sensitive data:

```bash
# Core secrets
oc create secret generic litellm-secrets \
  --from-literal=LITELLM_MASTER_KEY='sk-...' \
  --from-literal=LITELLM_SALT_KEY='sk-...' \
  --from-literal=DATABASE_URL='postgresql://...' \
  -n llm-service

# Redis secrets
oc create secret generic redis-secrets \
  --from-literal=REDIS_HOST='redis-service.redis.svc.cluster.local' \
  --from-literal=REDIS_PORT='6379' \
  --from-literal=REDIS_PASSWORD='...' \
  -n llm-service
```

## Customization Guide

### Adding a New Model

1. **Deploy vLLM backend** for your model
2. **Create Kubernetes Service** for the vLLM backend
3. **Add model entry** to `model_list`:

```yaml
- model_name: your-model-name
  litellm_params:
    model: openai/your-model-name
    api_base: http://vllm-your-model-service.llm-service.svc.cluster.local:8000/v1
    api_key: dummy-key
  rpm: 500  # Adjust based on model size/performance
  tpm: 40000
  model_info:
    supported_environments: ["production"]
```

### Adjusting Rate Limits

**RPM (Requests Per Minute):**
- Small models (7B): 600-800 RPM
- Medium models (13B): 400-600 RPM
- Large models (70B+): 100-200 RPM

**TPM (Tokens Per Minute):**
- Small models: 50,000-60,000 TPM
- Medium models: 30,000-40,000 TPM
- Large models: 20,000-30,000 TPM

### Load Balancing

To add more instances for load balancing, duplicate the model entry with a different `api_base`:

```yaml
# Instance 1
- model_name: llama-2-7b
  litellm_params:
    api_base: http://vllm-llama-2-7b-service.llm-service.svc.cluster.local:8000/v1

# Instance 2 (for load balancing)
- model_name: llama-2-7b
  litellm_params:
    api_base: http://vllm-llama-2-7b-service-2.llm-service.svc.cluster.local:8000/v1
```

LiteLLM will automatically distribute requests across instances using the `simple-shuffle` routing strategy.

## Deployment

### 1. Create ConfigMap

```bash
oc create configmap litellm-config \
  --from-file=config.yaml=./litellm-config-local-models.yaml \
  -n llm-service
```

### 2. Deploy LiteLLM

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-proxy
  namespace: llm-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: litellm
        image: docker.litellm.ai/berriai/litellm-database:main-stable
        args:
          - "--port"
          - "4000"
          - "--config"
          - "/app/config.yaml"
          - "--num_workers"
          - "$(nproc)"
        env:
        - name: LITELLM_MODE
          value: "PRODUCTION"
        - name: LITELLM_LOG
          value: "ERROR"
        envFrom:
        - secretRef:
            name: litellm-secrets
        - secretRef:
            name: redis-secrets
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
      volumes:
      - name: config
        configMap:
          name: litellm-config
```

### 3. Verify Deployment

```bash
# Check pods
oc get pods -n llm-service

# Check logs
oc logs -f deployment/litellm-proxy -n llm-service

# Test endpoint
curl http://litellm-service.llm-service.svc.cluster.local:4000/health
```

## Testing

### Test Model Availability

```bash
curl http://litellm-service.llm-service.svc.cluster.local:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

### Test Model Request

```python
import openai

client = openai.OpenAI(
    api_key="dummy-key",  # Or use virtual key from /key/generate
    base_url="http://litellm-service.llm-service.svc.cluster.local:4000"
)

response = client.chat.completions.create(
    model="llama-2-7b",
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

## Performance Tuning

### Database Connection Pool

Calculate based on your setup:

```
database_connection_pool_limit = MAX_DB_CONNECTIONS / (instances × workers)
```

Example: 100 max connections, 3 instances, 4 workers = 100/(3×4) = 8.33 → use 10

### Redis Configuration

**Required for:**
- Multi-instance load balancing
- Shared rate limiting (rpm/tpm) across instances
- Response caching
- High traffic (1000+ RPS) transaction buffering

**Redis Version:** 7.0+ required

### Worker Configuration

Match workers to CPU count:

```bash
--num_workers $(nproc)
```

For memory leak mitigation:

```bash
--max_requests_before_restart 10000
--run_gunicorn  # More stable worker recycling
```

## Monitoring

### Key Metrics

- **Request rate**: Requests per second per model
- **Latency**: P50, P95, P99 response times
- **Error rate**: Failed requests percentage
- **Model utilization**: Which models are being used
- **Rate limit hits**: When rpm/tpm limits are reached

### Health Checks

LiteLLM provides health endpoints:

- `/health/liveliness`: Pod liveness check
- `/health/readiness`: Pod readiness check

Enable separate health app for better reliability:

```bash
export SEPARATE_HEALTH_APP=1
export SEPARATE_HEALTH_PORT=8001
```

## Troubleshooting

### Model Not Available

**Check:**
1. vLLM service is running: `oc get svc -n llm-service`
2. vLLM pods are healthy: `oc get pods -n llm-service`
3. Service DNS name is correct in config
4. Network policies allow traffic

### High Latency

**Check:**
1. vLLM GPU utilization
2. Redis latency
3. Database connection pool limits
4. Network between LiteLLM and vLLM

### Rate Limit Issues

**Check:**
1. Redis is configured correctly
2. `rpm`/`tpm` values are appropriate
3. Multiple instances are properly configured

### Connection Errors

**Check:**
1. Service DNS names are correct
2. Network policies allow traffic
3. vLLM backends are accessible
4. Port numbers match (default: 8000)

## Security Considerations

### Network Policies

Restrict traffic to only necessary services:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: litellm-policy
  namespace: llm-service
spec:
  podSelector:
    matchLabels:
      app: litellm
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: llm-service  # Allow access to vLLM services
    ports:
    - protocol: TCP
      port: 8000
```

### API Keys

- Use virtual keys via `/key/generate` endpoint
- Store `LITELLM_MASTER_KEY` in OpenShift Secrets
- Rotate keys regularly (except `LITELLM_SALT_KEY`)

## Best Practices

1. **Use version tags** for Docker images, not `latest`
2. **Enable separate health app** for better reliability
3. **Set appropriate rate limits** based on model size
4. **Monitor Redis and database** connections
5. **Use JSON logging** for log aggregation
6. **Enable caching** for frequently used models
7. **Configure fallbacks** for high availability
8. **Test failover** scenarios regularly

## References

- [LiteLLM Documentation](https://docs.litellm.ai)
- [vLLM Documentation](https://docs.vllm.ai)
- [Production Configuration Guide](./litellm-production-configuration-guide.md)
- [LLM Architecture Document](./llm-as-a-service-architecture.md)
