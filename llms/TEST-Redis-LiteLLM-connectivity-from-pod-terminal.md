# Test Redis ↔ LiteLLM Connectivity From Pod Terminal

How to test the connection between the Redis pod and the LiteLLM pod using the **terminal inside a pod** (OpenShift UI or kubectl).

---

## 1. Open a terminal in a pod

### Option A: OpenShift UI

1. Go to **Workloads** → **Pods**.
2. Select your **namespace** (e.g. `llm-platform` for LiteLLM, or the namespace where Redis/LiteLLM run).
3. Click the **LiteLLM pod** (or the Redis pod, depending on which side you want to test from).
4. Open the **Terminal** tab (or **Exec** / **Open terminal**).
5. Choose the container if the pod has more than one (e.g. `litellm` or `redis-enterprise-node`).
6. You get a shell inside the pod.

### Option B: kubectl / oc

```bash
# Terminal into LiteLLM pod (replace <namespace> and <pod-name>)
kubectl exec -it <litellm-pod-name> -n <namespace> -- sh

# Or if the container has bash:
kubectl exec -it <litellm-pod-name> -n <namespace> -- bash
```

**Find pod names:**

```bash
# LiteLLM pods
kubectl get pods -n llm-platform -l app=litellm

# Redis pods (Redis Enterprise: rec-0, rec-1, rec-2 or the REDB service name)
kubectl get pods -n <redis-namespace>
```

---

## 2. From LiteLLM pod → test connection to Redis

From inside the **LiteLLM** pod you can test reachability of Redis using the same host/port LiteLLM uses.

### Step 1: Get Redis host and port (inside LiteLLM pod)

```bash
# Inside LiteLLM pod
echo $REDIS_HOST
echo $REDIS_PORT
```

If not set, check your deployment (e.g. `REDIS_HOST=redis.llm-data.svc.cluster.local`, `REDIS_PORT=6379`), or for Redis Enterprise the DB service name (e.g. `my-redb.redis-enterprise.svc.cluster.local` and port often `12000` or `6379`).

### Step 2: Test TCP connectivity to Redis

**Using `nc` (netcat):**

```bash
# Replace with your REDIS_HOST and REDIS_PORT
nc -zv $REDIS_HOST $REDIS_PORT
# Example: nc -zv redis.llm-data.svc.cluster.local 6379
```

- `-z`: scan, no data sent  
- `-v`: verbose  
- If it says “succeeded” or “open”, TCP works.

**Using `timeout` if `nc` doesn’t support `-z`:**

```bash
timeout 3 bash -c "echo >/dev/tcp/$REDIS_HOST/$REDIS_PORT" && echo "OK" || echo "FAIL"
```

**Using `telnet` (if available):**

```bash
telnet $REDIS_HOST $REDIS_PORT
# Type Ctrl+] then quit to exit
```

### Step 3: Test Redis protocol (PING) from LiteLLM pod

If the image has **redis-cli**:

```bash
# With password (get from REDIS_PASSWORD or your secrets)
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a "$REDIS_PASSWORD" PING
# Expected: PONG
```

If redis-cli is not installed, the TCP test (Step 2) is enough to confirm “pod can reach Redis”.

---

## 3. From Redis pod → test connection to LiteLLM

From inside a **Redis** pod (e.g. Redis Enterprise node or a sidecar that has `curl`), you can test reachability of LiteLLM.

### LiteLLM service address

- **Service name:** `litellm-service` (or whatever your LiteLLM service is called).
- **Namespace:** e.g. `llm-platform`.
- **Port:** `8000`.

**Full DNS (from another namespace):**

```text
litellm-service.llm-platform.svc.cluster.local
```

**If Redis and LiteLLM are in the same namespace:**

```text
litellm-service
```

### Test from Redis pod

**Using `curl` (if available in the Redis pod):**

```bash
# Same namespace
curl -s -o /dev/null -w "%{http_code}" http://litellm-service:8000/health

# Different namespace (e.g. from redis-enterprise namespace)
curl -s -o /dev/null -w "%{http_code}" http://litellm-service.llm-platform.svc.cluster.local:8000/health
```

- HTTP 200 = LiteLLM health endpoint is reachable.

**Using `nc`:**

```bash
# Same namespace
nc -zv litellm-service 8000

# Different namespace
nc -zv litellm-service.llm-platform.svc.cluster.local 8000
```

**Using `wget`:**

```bash
wget -q -O- http://litellm-service.llm-platform.svc.cluster.local:8000/health
```

---

## 4. Quick reference

| Test direction   | From pod   | Target              | Command (example) |
|------------------|------------|---------------------|------------------------------------------|
| LiteLLM → Redis  | LiteLLM    | Redis host:port     | `nc -zv $REDIS_HOST $REDIS_PORT`          |
| LiteLLM → Redis  | LiteLLM    | Redis PING          | `redis-cli -h $REDIS_HOST -p $REDIS_PORT -a "$REDIS_PASSWORD" PING` |
| Redis → LiteLLM  | Redis      | LiteLLM :8000       | `curl -s http://litellm-service.llm-platform.svc.cluster.local:8000/health` |
| Redis → LiteLLM  | Redis      | LiteLLM :8000       | `nc -zv litellm-service.llm-platform.svc.cluster.local 8000` |

---

## 5. Namespace and service names

- **LiteLLM:** usually in `llm-platform`, service `litellm-service`, port `8000`.
- **Redis (standalone):** e.g. `llm-data`, service `redis`, port `6379`.
- **Redis Enterprise:** REC in e.g. `redis-enterprise`; the **database** is exposed by a service (often named like the REDB, e.g. `my-redb`), port often `12000` or `6379`.

Use the same **host** and **port** in the pod that LiteLLM uses for Redis (from env or config). Then run the TCP or redis-cli tests from the LiteLLM pod, and the curl/nc tests to LiteLLM from the Redis pod.

---

## 6. Troubleshooting

- **Connection refused / timeout from LiteLLM to Redis**  
  Check: Redis service exists, correct port, NetworkPolicy allows LiteLLM → Redis, and (if applicable) Redis Enterprise DB is up and reachable.

- **Connection refused / timeout from Redis to LiteLLM**  
  Check: LiteLLM service and port (8000), NetworkPolicy allows Redis → LiteLLM, and correct namespace in the DNS name.

- **`nc` / `redis-cli` / `curl` not found**  
  Use another tool (e.g. `timeout` + `/dev/tcp`, or install a minimal client in the image). TCP test is enough to confirm connectivity.

- **Wrong host/port**  
  Inspect LiteLLM env: `kubectl exec -it <litellm-pod> -n llm-platform -- env | grep REDIS`.

Using the pod terminal like this is the same as “from Redis pod” and “from LiteLLM pod” – you’re just running the commands inside each pod’s shell.
