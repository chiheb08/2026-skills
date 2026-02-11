# Where to configure rec-services-rigger to talk to the rec service

**Short answer:** You do **not** configure rec-services-rigger separately. The operator deploys it and it talks to the REC using the **RedisEnterpriseCluster name** as the service hostname. The only thing you set is the **REC name** in your cluster manifest.

---

## 1. How it works

- The **Redis Enterprise Operator** creates (among other things):
  - The REC pods (rec-0, rec-1, …).
  - A **Kubernetes Service** whose name is the **same as the REC name** (e.g. if the REC is named `rec`, the service is `rec`; if named `my-rec`, the service is `my-rec`).
  - The **rec-services-rigger** deployment, which calls the REC REST API at **`<REC-name>:9443`** (e.g. `rec:9443` or `my-rec:9443`).

- The operator knows the REC name from the **RedisEnterpriseCluster** resource and wires rec-services-rigger to use that name. There is **no separate URL or host/port config** for rec-services-rigger in your YAML; it’s implicit from the REC.

---

## 2. The only “configuration” you do: REC name

Set the **RedisEnterpriseCluster** `metadata.name` in the same namespace where the operator runs. That name becomes the Service name and the hostname rec-services-rigger uses.

Example — **rec.yaml** (REC name = `rec`):

```yaml
apiVersion: app.redislabs.com/v1
kind: RedisEnterpriseCluster
metadata:
  name: rec          # → Service name is "rec" → rec-services-rigger uses rec:9443
  namespace: redis-enterprise
spec:
  nodes: 3
  # ...
```

Example — REC name = `my-rec`:

```yaml
metadata:
  name: my-rec       # → Service name is "my-rec" → rec-services-rigger uses my-rec:9443
```

So: **where you configure** rec-services-rigger’s target is **in the REC manifest**, by setting **`metadata.name`** of the **RedisEnterpriseCluster**. No other YAML is needed for “pointing” rec-services-rigger at the rec service.

---

## 3. What you must ensure (not in REC spec)

These are **cluster/network** requirements, not fields in the REC:

| Requirement | Why |
|-------------|-----|
| **Same namespace** | rec-services-rigger and the Service `rec` (or `my-rec`) must be in the same namespace so DNS `<REC-name>:9443` resolves. The operator deploys both in the REC’s namespace. |
| **Service has endpoints** | The Service must have at least one endpoint (REC pod Running and Ready). Otherwise `rec:9443` has no backend. |
| **NetworkPolicy** | If you use NetworkPolicies, allow **ingress to REC pods on port 9443** from rec-services-rigger (and operator). See `redis-enterprise-network-policy.yaml` and the 9443 timeout troubleshooting docs. |

---

## 4. Summary

| Question | Answer |
|----------|--------|
| Where do I set the rec-services-rigger → rec URL? | You don’t. The operator uses the REC name as the service hostname. |
| Where do I set the REC / service name? | In **RedisEnterpriseCluster** `metadata.name` (e.g. in **rec.yaml**). |
| What if my REC is named `my-rec`? | The service is `my-rec`; rec-services-rigger talks to `my-rec:9443`. |
| What if connectivity fails? | Check same namespace, Service endpoints, and NetworkPolicy (see SOLUTION-rec-9443-timeout.md and TROUBLESHOOT-UI-step-by-step.md). |

So: **configure the REC name in the RedisEnterpriseCluster manifest (rec.yaml)**; that is what defines which service rec-services-rigger talks to. No separate rec-services-rigger connection config is required.
