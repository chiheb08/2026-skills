# Message to Security Team: Request for anyuid SCC

## Short Version (Copy-paste ready)

---

**Subject:** Request: anyuid SCC for Redis Enterprise Cluster pods

Hi [Security Team],

We're deploying Redis Enterprise Cluster (REC) on OpenShift and encountering an issue where the pods cannot execute required components (`pdns_server`) due to Security Context Constraints (SCC).

**Current situation:**
- REC pods are using `nonroot-v2` SCC
- The `pdns_server` component exits with status 126 (cannot execute)
- This prevents the cluster from bootstrapping properly

**Request:**
We need to add `anyuid` SCC to the ServiceAccount used by our REC pods to allow the required components to execute.

**Details:**
- **Namespace:** [your namespace, e.g. `redis-enterprise`]
- **ServiceAccount:** [ServiceAccount name from `kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}'`]
- **SCC needed:** `anyuid`
- **Command:** `oc adm policy add-scc-to-user anyuid -z <service-account-name> -n <namespace>`

**Security note:**
We understand that `anyuid` allows pods to run as any user ID (including root). This is required for Redis Enterprise components to function correctly. The REC pods will be isolated within their namespace and will only be used for Redis Enterprise operations.

**Alternative:**
If `anyuid` is not allowed, please let us know what alternative SCC or configuration would work for this use case.

Thank you for your review.

---

## Longer Version (If more context is needed)

---

**Subject:** Request: anyuid SCC for Redis Enterprise Cluster - Security Review

Hi [Security Team],

We're deploying Redis Enterprise Cluster (REC) on OpenShift and need your approval to use `anyuid` Security Context Constraint (SCC) for our REC pods.

**Problem:**
Our REC pods are currently using `nonroot-v2` SCC, which is blocking the execution of required Redis Enterprise components (specifically `pdns_server`). The component exits with status 126 (cannot execute), preventing the cluster from bootstrapping and becoming operational.

**Technical details:**
- **Namespace:** [your namespace]
- **ServiceAccount:** [ServiceAccount name]
- **Current SCC:** `nonroot-v2`
- **Required SCC:** `anyuid`
- **Impact:** Without this, REC pods cannot complete bootstrap and remain in a non-functional state

**What we need:**
Permission to add `anyuid` SCC to our REC ServiceAccount using:
```bash
oc adm policy add-scc-to-user anyuid -z <service-account-name> -n <namespace>
```

**Security considerations:**
- `anyuid` allows pods to run as any user ID (including root)
- REC pods will be isolated within their dedicated namespace
- Pods will only be used for Redis Enterprise operations
- We follow standard security practices (NetworkPolicies, RBAC, etc.)

**Questions:**
1. Is `anyuid` SCC allowed for this use case?
2. If not, what alternative SCC or configuration would you recommend?
3. Are there any additional security controls we should implement?

Thank you for your time and review.

---

## Even Shorter Version (Quick email)

---

**Subject:** SCC Request: anyuid for Redis Enterprise pods

Hi,

We need `anyuid` SCC for our Redis Enterprise Cluster pods. Current `nonroot-v2` SCC is blocking required components from executing (exit 126).

**Namespace:** [namespace]  
**ServiceAccount:** [sa-name]  
**Command:** `oc adm policy add-scc-to-user anyuid -z <sa-name> -n <namespace>`

Can you approve this or suggest an alternative?

Thanks!

---

## Tips for sending the message

1. **Fill in the placeholders:**
   - `[Security Team]` → Actual team/person name
   - `[your namespace]` → Your namespace (e.g. `redis-enterprise`)
   - `[ServiceAccount name]` → Run: `kubectl get pod rec-0 -n <namespace> -o jsonpath='{.spec.serviceAccountName}'`

2. **Choose the version:**
   - **Short version** → Good for teams familiar with SCCs
   - **Longer version** → Good if they need more context
   - **Even shorter** → Good for quick approval requests

3. **Be ready to answer:**
   - Why Redis Enterprise needs this
   - What security measures you have in place
   - If there are alternatives you've tried
