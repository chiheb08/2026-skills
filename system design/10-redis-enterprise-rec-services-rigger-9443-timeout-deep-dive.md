# Redis Enterprise — Deep Dive: rec-services-rigger "get https://rec:9443/v1/nodes: context deadline exceeded"

This document explains **why** the `rec-services-rigger` pod logs `get https://rec:9443/v1/nodes: context deadline exceeded (Client.Timeout exceeded while awaiting headers)` and **how to fix it** step by step.

---

## 1. What is rec-services-rigger and what is https://rec:9443/v1/nodes?

- **rec-services-rigger** is a pod created by the Redis Enterprise operator for each Redis Enterprise Cluster (REC). It runs the **Services Manager** (formerly "k8s-controller") image and handles operational tasks: configuring services, routing, and talking to the REC REST API.
- **https://rec:9443** is the REC’s REST API. The hostname **`rec`** is the Kubernetes **Service** for your REC (same name as the REC). Port **9443** is the default HTTPS port for the Redis Enterprise REST API (cluster management, `/v1/nodes`, databases, etc.).
- **GET /v1/nodes** returns the list of nodes in the cluster. The services-rigger calls this (and other API endpoints) to configure services and keep state in sync with the cluster.

So: **rec-services-rigger** needs to reach the **rec** Service (which targets REC pods like `rec-0`, `rec-1`) on port **9443**. If that request times out, you see "context deadline exceeded" / "Client.Timeout exceeded while awaiting headers".

---

## 2. Why does the request to rec:9443 time out?

Common causes:

| Cause | What happens |
|-------|----------------|
| **1. Service "rec" has no endpoints** | The Service **rec** selects REC pods (e.g. `rec-0`, `rec-1`). If those pods are not **Ready**, the Service has no endpoints. Traffic to `rec:9443` goes nowhere and the client times out. |
| **2. REC pods not listening on 9443 yet** | Port 9443 is the REST API. It becomes available only after the node has **joined the cluster** and the API is up. If the first node (`rec-0`) is still bootstrapping (e.g. creating cluster, or not ready), 9443 may not be listening yet. The services-rigger can start before the API is ready. |
| **3. NetworkPolicy blocking rec-services-rigger → rec** | If you use NetworkPolicies and only allow specific pod labels to reach REC pods, **rec-services-rigger** might not match those labels. Then ingress to the REC pods (and thus to `rec:9443`) is denied and the client times out. |
| **4. REC pods not running or crash-looping** | If `rec-0` (and peers) are not Running (e.g. PVC, image pull, memory, or SCC issues), the Service never gets endpoints and 9443 is never reachable. |
| **5. Wrong namespace or wrong service name** | The services-rigger must resolve **rec** in the same namespace as the REC. If the Service is missing or in another namespace, the request fails or times out. |

In practice, **cause 1 and 2** (Service has no endpoints / REC not ready yet) and **cause 3** (NetworkPolicy) are the most common.

---

## 3. Step-by-step fix (in order)

Use the namespace where your REC and rec-services-rigger run (e.g. `redis-enterprise`). Replace `rec` with your REC name if different.

---

### Step 1 — Check Service "rec" and its endpoints

```bash
export NS=redis-enterprise   # or your REC namespace
kubectl get svc rec -n $NS -o wide
kubectl get endpoints rec -n $NS -o yaml
```

- **If the Service does not exist** → The operator may not have created it yet. Ensure the REC is created and the operator has finished creating the StatefulSet and Service (see Step 2). Fix any "rec-bulletin-board not found" or "object has been modified" issues first.
- **If the Service exists but Endpoints are empty** (no addresses) → No REC pod is Ready yet. The services-rigger cannot reach `rec:9443`. Go to Step 2 and get REC pods Running and Ready.

---

### Step 2 — Check REC pods (rec-0, rec-1, …) are Running and Ready

```bash
kubectl get pods -n $NS -l app=rec    # or the label your REC pods use
kubectl get pods -n $NS | grep rec
kubectl describe pod rec-0 -n $NS     # look at Events and readiness
```

- **Pods not Running** → Fix pod startup (PVC, image pull secret, memory, SCC on OpenShift). See your existing REC troubleshooting docs (e.g. "Pod rec-0 not found", "Waiting for first pod to bootstrap").
- **Pods Running but not Ready** → The readiness probe may be failing. Port 9443 (or the probe port) must be listening. Wait for bootstrap to complete, or check logs of `rec-0`: `kubectl logs rec-0 -n $NS`.
- **Pods Ready** → The Service **rec** should have endpoints. Then check Step 3 (NetworkPolicy) and Step 4 (connectivity test).

---

### Step 3 — Ensure NetworkPolicy allows rec-services-rigger → rec:9443

If you have a NetworkPolicy that restricts **ingress to REC pods** (e.g. only from pods with labels `redis-enterprise`, `vllm`, `litellm-db`), then **rec-services-rigger** must be allowed too.

1. Check the labels on rec-services-rigger:
   ```bash
   kubectl get pod -n $NS -l app.kubernetes.io/name=redis-enterprise --show-labels
   kubectl get pods -n $NS | grep services-rigger
   kubectl get pod <rec-services-rigger-pod-name> -n $NS -o yaml | grep -A 20 labels
   ```

2. If rec-services-rigger does **not** have one of the labels you use in the NetworkPolicy ingress rules (e.g. `app.kubernetes.io/name: redis-enterprise`), add an ingress rule that allows traffic **from** the services-rigger pod. For example, if it has `app.kubernetes.io/component: services-rigger` or `app: rec`, add to your policy:
   - **From pods with** `app.kubernetes.io/component: services-rigger`, or  
   - **From pods with** `app: rec`  
   so that rec-services-rigger can reach the REC pods (and thus `rec:9443`).

An example policy file that includes a rule for rec-services-rigger is in `redis-enterprise-argocd-example/redis-enterprise-network-policy.yaml` (see the "From rec-services-rigger" rule). Apply the policy in the REC namespace.

---

### Step 4 — Test connectivity from rec-services-rigger to rec:9443

From inside the rec-services-rigger pod (or from any pod in the same namespace that is allowed by NetworkPolicy):

```bash
kubectl exec -it <rec-services-rigger-pod-name> -n $NS -- sh
# then inside the pod (if curl/wget available):
curl -k -v --connect-timeout 5 https://rec:9443/v1/nodes
# or
wget -O- --no-check-certificate https://rec:9443/v1/nodes
```

- **Connection refused / no route** → REC pods not listening on 9443 yet (bootstrap not finished) or NetworkPolicy still blocking. Re-check Steps 1–3.
- **Timeout** → Same as above: no endpoints, or policy blocking, or REC not ready.
- **HTTP 200 or 401** → Connectivity is fine; the original timeout may be due to a short client timeout or temporary unavailability. Consider increasing timeout or retries in the component that calls the API (if configurable).

---

### Step 5 — Bootstrap order and retries

The services-rigger often starts while the REC is still bootstrapping. The operator or the services-rigger image may retry. If the REC and Service become ready shortly after, the error may disappear on its own after a few minutes.

If the error persists:

1. Ensure **ignoreDifferences** and **no auto-sync** are set for the REC (Argo CD) so the operator can complete bootstrap and create the ConfigMap and pods (see your "rec-bulletin-board" troubleshooting doc).
2. Ensure **REC pods are Running and Ready** and the **rec** Service has endpoints (Steps 1–2).
3. Ensure **NetworkPolicy allows** rec-services-rigger to reach REC pods (Step 3).

---

### Step 6 — Summary checklist

| Check | Command / action |
|-------|-------------------|
| Service **rec** exists | `kubectl get svc rec -n $NS` |
| Service has endpoints | `kubectl get endpoints rec -n $NS` |
| REC pods Running & Ready | `kubectl get pods -n $NS \| grep rec` |
| rec-services-rigger labels | `kubectl get pod <rec-services-rigger> -n $NS -o yaml \| grep -A 20 labels` |
| NetworkPolicy allows services-rigger → rec | Add ingress rule for services-rigger pod label (see Step 3 and example policy). |
| Test from pod to rec:9443 | `kubectl exec ... curl -k -v https://rec:9443/v1/nodes` |

---

## 4. Root cause and fix summary

| Root cause | Fix |
|------------|-----|
| **Service rec has no endpoints** | Get REC pods (rec-0, …) Running and Ready; fix PVC, image, memory, SCC. |
| **REC not listening on 9443 yet** | Wait for bootstrap; fix operator/Argo CD conflict and "rec-bulletin-board" so bootstrap can complete. |
| **NetworkPolicy blocking rec-services-rigger** | Add ingress rule so pods with rec-services-rigger’s label (e.g. `app.kubernetes.io/component: services-rigger` or `app: rec`) can reach REC pods. |
| **REC pods not running** | Fix pod startup (see REC troubleshooting: PVC, image pull, memory, SCC). |

The "get https://rec:9443/v1/nodes: context deadline exceeded" message means the client in rec-services-rigger could not get a response from the REC API in time. Ensuring the **rec** Service has endpoints, REC pods are Ready, and **NetworkPolicy allows rec-services-rigger → rec** usually resolves it.
