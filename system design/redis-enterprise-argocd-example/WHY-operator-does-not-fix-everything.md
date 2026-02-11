# Why the operator doesn't fix everything automatically

You're right to expect automation, but there are **limits to what the Redis Enterprise Operator controls**. Here's what it does vs. what it doesn't.

---

## What the operator DOES automatically

The **Redis Enterprise Operator** automatically:

1. ✅ **Creates REC pods** (rec-0, rec-1, rec-2) when you set `spec.nodes: 3`
2. ✅ **Creates the Service "rec"** with the correct selector (e.g. `app: redis-enterprise`, `redis.io/cluster: rec`)
3. ✅ **Creates rec-services-rigger** deployment
4. ✅ **Manages lifecycle** (scaling, updates, deletions)
5. ✅ **Configures REC nodes** (joins them to the cluster, sets up internode communication)

So yes, the operator **creates the Service "rec"** and **creates the pods**. That part is automatic.

---

## What the operator CANNOT control (and why you see errors)

### 1. **Service endpoints are populated by Kubernetes, not the operator**

- The operator creates the **Service** with a selector (e.g. `app: redis-enterprise`, `redis.io/cluster: rec`).
- **Kubernetes control plane** (not the operator) watches pods and **automatically adds pods to Service endpoints** when:
  - Pod labels **match** the Service selector
  - Pod is **Ready** (readiness probe passes, or no probe = container running)

**Why endpoints might be empty:**
- Pods exist but are **not Ready** (still bootstrapping, CrashLoopBackOff, etc.)
- Pod labels **don't match** the Service selector (rare, but possible if labels changed)

**The operator cannot force endpoints to populate** — that's Kubernetes behavior. If rec-0 is Running but not Ready, Kubernetes won't add it to endpoints until it's Ready.

---

### 2. **NetworkPolicies are NOT created by the operator**

**Why:**
- NetworkPolicies are **environment-specific** (dev vs prod might have different rules)
- They're often managed by **platform/security teams**, not application operators
- The operator doesn't know what other pods/services need to talk to the REC
- Some clusters don't use NetworkPolicies at all (default allow)

**What happens without NetworkPolicies:**
- If your cluster has a **default-deny NetworkPolicy** (common in OpenShift with OVN-Kubernetes or Calico), **all traffic is blocked** unless explicitly allowed.
- The operator creates pods, but if NetworkPolicy blocks traffic, rec-services-rigger **cannot reach rec:9443** → timeout errors.

**The operator cannot create NetworkPolicies** because it doesn't know your security requirements. You (or your platform team) must create them.

---

### 3. **Pod readiness depends on REC bootstrap, not just operator**

The operator creates pods, but pods become **Ready** only when:
- Container starts successfully
- **Readiness probe passes** (if configured)
- For REC nodes: the **REC node finishes bootstrapping** and port **9443** (REST API) is available

**Why rec-0 might be Running but not Ready:**
- Still bootstrapping (can take several minutes)
- Storage/PVC issues
- Resource limits (CPU/memory)
- Security context constraints (SCC) blocking startup
- Image pull issues

**The operator cannot make pods Ready faster** — it waits for Kubernetes readiness probes and REC bootstrap.

---

### 4. **Sequential node creation (rec-0 → rec-1 → rec-2)**

The operator often creates nodes **one at a time**:
1. Create rec-0 → wait for it to be Ready and cluster API (rec:9443) reachable
2. Create rec-1 → wait for it to join and be Ready
3. Create rec-2 → wait for it to join and be Ready

**Why rec-1 and rec-2 might not exist:**
- If rec-services-rigger (or operator) **cannot reach rec:9443** (NetworkPolicy blocking), the operator considers the cluster "not ready" and **doesn't create rec-1/rec-2**.
- This is a **safety feature** — don't add more nodes if the cluster API isn't reachable.

**The operator cannot create rec-1/rec-2** until rec:9443 is reachable and rec-0 is fully operational.

---

## Summary: What causes the errors

| Error | Why it happens | What the operator does | What you must do |
|-------|----------------|------------------------|------------------|
| **Service rec has no endpoints** | rec-0 is Running but **not Ready** (still bootstrapping) | Operator created rec-0 and Service rec | Wait for rec-0 to finish bootstrapping, or fix pod startup issues (storage, resources, SCC) |
| **"get https://rec:9443/v1/nodes: context deadline exceeded"** | **NetworkPolicy blocks** rec-services-rigger → rec:9443 | Operator created pods and Service, but **cannot create NetworkPolicies** | Create NetworkPolicies that allow traffic to REC pods on 9443 from rec-services-rigger |
| **Only rec-0 exists, no rec-1/rec-2** | Operator is waiting for rec:9443 to be reachable before creating more nodes | Operator created rec-0, but **won't create rec-1/rec-2** until cluster API is reachable | Fix rec:9443 connectivity (NetworkPolicy), then operator will create rec-1/rec-2 |

---

## The bottom line

**The operator automates REC resource creation and lifecycle**, but it **cannot control**:
- **Kubernetes networking** (NetworkPolicies, Service endpoints population)
- **Pod readiness** (depends on REC bootstrap, storage, resources)
- **Cluster security policies** (SCC, quotas, NetworkPolicies)

So when you see:
- ✅ **"Everything synced in Argo CD"** → Operator created all resources correctly
- ❌ **"rec-services-rigger timeout to rec:9443"** → **NetworkPolicy is blocking** (operator cannot fix this)
- ❌ **"Service rec has no endpoints"** → **rec-0 is not Ready yet** (operator created it, but Kubernetes won't add it to endpoints until Ready)

**You must fix NetworkPolicies and pod readiness** — the operator cannot do that for you.

---

## What to do

1. **Fix NetworkPolicies** (if your cluster uses them) — allow traffic to REC pods on 9443 from rec-services-rigger. See `redis-enterprise-network-policy.yaml`.
2. **Wait for rec-0 to be Ready** (or fix pod startup issues if it's stuck).
3. **Restart rec-services-rigger** after fixing NetworkPolicies so it retries rec:9443.
4. **Wait for operator to create rec-1/rec-2** after rec:9443 is reachable.

The operator will handle the rest automatically once networking and readiness are fixed.
