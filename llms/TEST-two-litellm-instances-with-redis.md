# Testing Two LiteLLM Instances with Redis — What Your Colleague Wants

**Your colleague asked you to test 2 LiteLLM instances with Redis, likely related to "tokens" or rate limiting.**

**Most likely goal:** Verify that **rate limits (RPM/TPM)** are enforced **globally across both instances**, not per-instance.

---

## What They're Testing: Shared Rate Limiting

### The Problem Without Redis

**Without Redis (or with misconfigured Redis):**
- Instance 1 enforces: "100 requests per minute" → allows 100 requests
- Instance 2 enforces: "100 requests per minute" → allows 100 requests
- **Total allowed: 200 requests per minute** ❌ (limit × number of instances)

**With Redis (correctly configured):**
- Both instances share the **same counters** in Redis
- Instance 1: checks Redis → "45 requests so far" → allows request → increments to 46
- Instance 2: checks Redis → "46 requests so far" → allows request → increments to 47
- **Total allowed: 100 requests per minute** ✅ (global limit)

### What to Test

**Goal:** Verify that rate limits are **global**, not per-instance.

**Test scenario:**
1. Deploy **2 LiteLLM instances** (both connected to the same Redis)
2. Set a rate limit (e.g., `rpm: 100` for a test key/model)
3. Send requests to **both instances** (alternating or in parallel)
4. **Expected:** After 100 total requests (across both instances), the 101st request should be rejected (429) **regardless of which instance** receives it

---

## How to Set Up the Test

### Step 1: Deploy 2 LiteLLM Instances

**Option A: Scale Deployment**

```bash
# Scale your existing LiteLLM deployment to 2 replicas
kubectl scale deployment litellm-proxy --replicas=2 -n llm-platform

# Verify both pods are running
kubectl get pods -n llm-platform -l app=litellm
```

**Option B: Create Separate Deployments**

Create 2 separate deployments (e.g., `litellm-proxy-1` and `litellm-proxy-2`) both pointing to the same Redis.

### Step 2: Verify Redis Configuration

**Both instances must use the same Redis:**

```yaml
# In your LiteLLM config.yaml or Deployment env vars
router_settings:
  redis_host: os.environ/REDIS_HOST  # Same Redis for both instances
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD
```

**Check that both pods have Redis env vars:**

```bash
# Check pod 1
kubectl exec -it litellm-proxy-<pod-1> -n llm-platform -- env | grep REDIS

# Check pod 2
kubectl exec -it litellm-proxy-<pod-2> -n llm-platform -- env | grep REDIS
```

Both should show the same `REDIS_HOST` and `REDIS_PORT`.

### Step 3: Set Up a Test Rate Limit

**In your LiteLLM config.yaml, set a low rate limit for testing:**

```yaml
model_list:
  - model_name: llama-2-7b
    litellm_params:
      model: openai/my-vllm-endpoint
      api_base: http://vllm-service:8000/v1
    model_info:
      rpm: 10  # Low limit for easy testing (10 requests per minute)
      tpm: 1000
```

**Or set rate limit per API key** (if using virtual keys):

```yaml
# In your config or via LiteLLM API
# Set rpm: 10, tpm: 1000 for a test key
```

### Step 4: Run the Test

**Test script (send requests to both instances):**

```bash
#!/bin/bash

# Get service endpoints for both instances
INSTANCE1="http://litellm-proxy-1.llm-platform.svc.cluster.local:8000"
INSTANCE2="http://litellm-proxy-2.llm-platform.svc.cluster.local:8000"
# Or if using a single service with load balancer:
# SERVICE="http://litellm-service.llm-platform.svc.cluster.local:8000"

API_KEY="your-test-api-key"
MODEL="llama-2-7b"

# Send 15 requests (5 more than the limit of 10)
for i in {1..15}; do
  echo "Request $i:"
  
  # Alternate between instances (or use load balancer)
  if [ $((i % 2)) -eq 0 ]; then
    ENDPOINT="$INSTANCE1"
  else
    ENDPOINT="$INSTANCE2"
  fi
  
  # Send request
  RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"$MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello $i\"}]}" \
    "$ENDPOINT/v1/chat/completions")
  
  HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
  
  if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ Success (instance: $ENDPOINT)"
  elif [ "$HTTP_CODE" = "429" ]; then
    echo "  ❌ Rate limit exceeded (instance: $ENDPOINT)"
  else
    echo "  ⚠️  Other error: $HTTP_CODE"
  fi
  
  sleep 1  # Small delay between requests
done
```

**Expected result:**
- Requests 1-10: ✅ Success (200)
- Request 11+: ❌ Rate limit exceeded (429) **regardless of which instance** receives it

---

## What Else They Might Be Testing

### 1. Shared Response Cache

**Test:** Send the same request to Instance 1, then to Instance 2.

**Expected:** Instance 2 should return the cached response from Instance 1 (no LLM call).

```bash
# Request 1: Instance 1
curl -X POST http://litellm-proxy-1:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model": "llama-2-7b", "messages": [{"role": "user", "content": "What is 2+2?"}]}'

# Request 2: Instance 2 (same prompt)
curl -X POST http://litellm-proxy-2:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model": "llama-2-7b", "messages": [{"role": "user", "content": "What is 2+2?"}]}'

# Instance 2 should return cached response (faster, no LLM call)
```

### 2. Load Balancing State

**Test:** Verify that routing decisions (e.g., "least-busy") are consistent across instances.

**How:** Check LiteLLM logs to see if both instances route to the same backends based on shared state.

### 3. Token Counting / Spend Tracking

**Test:** Verify that token usage/spend is tracked correctly across both instances.

**How:** Send requests to both instances, then check PostgreSQL or LiteLLM admin API to verify total spend/tokens matches the sum from both instances.

---

## Quick Verification Commands

### Check Redis Connection from Both Pods

```bash
# Pod 1
kubectl exec -it litellm-proxy-<pod-1> -n llm-platform -- \
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a "$REDIS_PASSWORD" PING

# Pod 2
kubectl exec -it litellm-proxy-<pod-2> -n llm-platform -- \
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a "$REDIS_PASSWORD" PING
```

### Check Rate Limit Counters in Redis

```bash
# Connect to Redis
kubectl exec -it redis-pod -n llm-platform -- redis-cli

# List rate limit keys (LiteLLM uses patterns like litellm:ratelimit:*)
KEYS litellm:ratelimit:*

# Check a specific counter
GET litellm:ratelimit:your-key:llama-2-7b:2025-01-29-14:30
```

### Monitor LiteLLM Logs

```bash
# Watch logs from both instances
kubectl logs -f -l app=litellm -n llm-platform --tail=50

# Look for rate limit messages, Redis connection logs, cache hits/misses
```

---

## Common Issues

### Issue 1: Rate Limits Not Shared

**Symptom:** Each instance allows the full limit (e.g., 100 per instance = 200 total).

**Cause:** Redis not configured in `router_settings`, or instances using different Redis instances.

**Fix:** Ensure both instances have the same `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` in their config.

### Issue 2: Redis Connection Errors

**Symptom:** LiteLLM logs show Redis connection failures.

**Fix:** Check NetworkPolicy, Redis service, and environment variables.

### Issue 3: Cache Not Shared

**Symptom:** Instance 2 doesn't return cached responses from Instance 1.

**Fix:** Ensure `cache: true` and `cache_params` with Redis are configured in both instances' config.

---

## Summary

**What your colleague likely wants to test:**

✅ **Shared rate limiting (RPM/TPM)** — Verify that rate limits are global across both instances, not per-instance.

**How to test:**
1. Deploy 2 LiteLLM instances (both connected to the same Redis)
2. Set a low rate limit (e.g., `rpm: 10`)
3. Send requests to both instances
4. Verify that after 10 total requests (across both instances), the 11th request is rejected regardless of which instance receives it

**Other possible tests:**
- Shared response cache
- Load balancing state consistency
- Token counting/spend tracking across instances

**Key requirement:** Both instances must use the **same Redis** for shared state to work correctly.
