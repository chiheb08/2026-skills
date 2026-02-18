# Why REDIS_HOST is Empty in LiteLLM Pod — Explained

**Your situation:**
- `REDIS_HOST` = empty
- `REDIS_PORT` = `tcp://172.30.159.178:6379` (connection string format)

**Why this happens and how to fix it.**

---

## Why REDIS_HOST is Empty

### Possible Causes

1. **Misconfigured environment variables** — The deployment/secret might not have `REDIS_HOST` set, or it was set incorrectly.
2. **Wrong variable name** — Someone might have used `REDIS_URL` or put everything in `REDIS_PORT` instead of separating host and port.
3. **Deployment configuration issue** — The environment variables weren't properly set in the Deployment manifest or Secret.
4. **LiteLLM might still work** — LiteLLM might parse `REDIS_PORT` as a connection string when `REDIS_HOST` is empty (not recommended, but might work).

---

## What Should Be Configured

**LiteLLM expects separate environment variables:**

```bash
REDIS_HOST=redis-service.redis-enterprise.svc.cluster.local  # Service name or IP
REDIS_PORT=6379                                              # Just the port number
REDIS_PASSWORD=your-password                                 # Password (if required)
```

**NOT:**
```bash
REDIS_HOST=                                    # Empty ❌
REDIS_PORT=tcp://172.30.159.178:6379          # Connection string ❌
```

---

## How to Check Your Current Configuration

### Step 1: Check Deployment/Secret

**In OpenShift UI:**

1. Go to **Workloads** → **Deployments** → **litellm** (or your LiteLLM deployment name).
2. Open it → **YAML** tab.
3. Look for `spec.template.spec.containers[0].env` or `envFrom`.
4. Check if `REDIS_HOST` and `REDIS_PORT` are defined.

**Or check Secrets:**

1. Go to **Workloads** → **Secrets**.
2. Find your Redis secret (e.g. `redis-secrets`).
3. Open it → **YAML** tab.
4. Check what keys are defined (should have `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`).

### Step 2: Check All Redis-Related Environment Variables

**Inside LiteLLM pod:**

```bash
# Check all Redis-related env vars
env | grep -i redis

# Or check specific ones
echo "REDIS_HOST: ${REDIS_HOST:-<not set>}"
echo "REDIS_PORT: ${REDIS_PORT:-<not set>}"
echo "REDIS_PASSWORD: ${REDIS_PASSWORD:+<set>}"  # Shows if set (doesn't show value)
echo "REDIS_URL: ${REDIS_URL:-<not set>}"
```

---

## How to Fix It

### Option 1: Fix in Deployment Manifest (Recommended)

**Update your LiteLLM Deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-proxy
  namespace: llm-platform
spec:
  template:
    spec:
      containers:
      - name: litellm
        env:
        # Fix Redis configuration
        - name: REDIS_HOST
          value: "172.30.159.178"  # TODO: Replace with Redis service name (better) or IP
        - name: REDIS_PORT
          value: "6379"  # Just the port number, not tcp://...
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-secrets
              key: REDIS_PASSWORD
```

**Better: Use Service Name Instead of IP**

```yaml
- name: REDIS_HOST
  value: "my-redb.redis-enterprise.svc.cluster.local"  # Redis Enterprise DB service name
  # Or: "redis.llm-data.svc.cluster.local"  # If using standalone Redis
```

**Why service name is better:**
- IPs can change (e.g., service ClusterIP changes)
- Service names are stable and DNS-resolvable
- Works across namespace boundaries

### Option 2: Fix in Secret

**If Redis config comes from a Secret:**

```bash
# Update the secret (replace values with your actual Redis service)
oc create secret generic redis-secrets \
  --from-literal=REDIS_HOST='my-redb.redis-enterprise.svc.cluster.local' \
  --from-literal=REDIS_PORT='6379' \
  --from-literal=REDIS_PASSWORD='your-password' \
  --dry-run=client -o yaml | oc apply -f - -n llm-platform
```

**Then restart LiteLLM pods:**

```bash
kubectl rollout restart deployment litellm-proxy -n llm-platform
```

### Option 3: Check if LiteLLM Config Uses Different Variables

**Check LiteLLM config.yaml** (if you're using a ConfigMap):

```bash
# Check ConfigMap
kubectl get configmap litellm-config -n llm-platform -o yaml | grep -i redis
```

**LiteLLM config.yaml should reference:**

```yaml
router_settings:
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD
```

If the config references `REDIS_HOST` and `REDIS_PORT`, but the environment variables aren't set correctly, LiteLLM won't be able to connect to Redis properly.

---

## Why This Matters

### LiteLLM Configuration Pattern

LiteLLM's config.yaml uses:

```yaml
router_settings:
  redis_host: os.environ/REDIS_HOST    # Reads from REDIS_HOST env var
  redis_port: os.environ/REDIS_PORT    # Reads from REDIS_PORT env var
```

**If `REDIS_HOST` is empty:**
- LiteLLM might try to use `REDIS_PORT` as a connection string (if it contains `tcp://`)
- Or LiteLLM might fail to connect to Redis
- This can cause rate limiting, caching, and transaction buffering to fail

### Performance Impact

- Using connection strings (`tcp://...` or `redis_url`) is **~80 RPS slower** than separate host/port/password
- Your current setup might work but is suboptimal

---

## Quick Diagnostic Commands

**Check what's actually configured:**

```bash
# 1. Check deployment env vars
kubectl get deployment litellm-proxy -n llm-platform -o jsonpath='{.spec.template.spec.containers[0].env}' | jq

# 2. Check secrets
kubectl get secret redis-secrets -n llm-platform -o yaml | grep -A 10 "data:"

# 3. Check all env vars in pod
kubectl exec -it <litellm-pod> -n llm-platform -- env | grep -i redis

# 4. Check LiteLLM config
kubectl get configmap litellm-config -n llm-platform -o yaml | grep -A 5 redis
```

---

## Summary

**Why `REDIS_HOST` is empty:**
- Likely a configuration issue in your Deployment or Secret
- `REDIS_PORT` contains a connection string (`tcp://IP:PORT`) instead of just the port
- Environment variables weren't set correctly

**What to do:**
1. **Check your Deployment/Secret** — See what's actually configured
2. **Fix environment variables** — Set `REDIS_HOST` to the Redis service name (or IP), and `REDIS_PORT` to just `6379`
3. **Use service name** — Better than IP (e.g. `my-redb.redis-enterprise.svc.cluster.local`)
4. **Restart pods** — After fixing, restart LiteLLM pods to pick up new env vars

**The correct format:**
```bash
REDIS_HOST=my-redb.redis-enterprise.svc.cluster.local  # Service name
REDIS_PORT=6379                                       # Just port number
REDIS_PASSWORD=your-password                          # Password
```

This matches what LiteLLM expects and provides better performance than connection strings.
