# Why only rec-0 exists (no rec-1, rec-2)

You have `spec.nodes: 3` in your RedisEnterpriseCluster but only **rec-0** is present (Running and Ready). rec-1 and rec-2 are not created.

---

## 1. Most likely: operator is waiting for rec:9443

The Redis Enterprise Operator often **creates nodes one by one**. It creates **rec-0** first, then waits for the cluster to be usable (including the REC REST API at **rec:9443**) before creating **rec-1**, then **rec-2**.

If **rec-services-rigger** (or the operator) **cannot reach rec:9443** (e.g. "context deadline exceeded"), the operator may consider the cluster not ready and **never create rec-1 and rec-2**.

**What to do:**

1. **Fix rec:9443 connectivity** (see SOLUTION-rec-9443-timeout.md):
   - Ensure **NetworkPolicy** allows traffic to REC pods on port 9443 from rec-services-rigger and the operator.
   - Ensure service **rec** has **rec-0** in its endpoints.
   - Restart **rec-services-rigger** (and optionally the operator) after fixing.
2. After rec:9443 works and rec-services-rigger logs are clean, wait a few minutes and check again for **rec-1** (then rec-2). The operator may then create them.

---

## 2. Check REC status and StatefulSet

**In OpenShift UI (or kubectl):**

1. **RedisEnterpriseCluster**
   - Workloads → **Redis Enterprise Clusters** (or search for the REC by name).
   - Open your REC → **YAML** or **Details**.
   - Look at **status**: e.g. `nodes`, `readyNodes`, `state`. Some operators expose desired vs current node count here.
2. **StatefulSet**
   - Workloads → **StatefulSets**.
   - Find the StatefulSet that owns rec-0 (name often matches REC name, e.g. **rec**).
   - Check **Desired** / **Replicas**:
     - If it shows **1** → operator has only requested 1 replica so far (consistent with “waiting for rec:9443”).
     - If it shows **3** but only rec-0 exists → rec-1/rec-2 may be **Pending** (scheduling, PVC, or resources). Check **Pods** and filter by name; open any rec-1/rec-2 and check **Events** and **Conditions**.

---

## 3. Argo CD and the REC / StatefulSet

- The **StatefulSet** is usually **created and owned by the operator**, not by your Git manifests. Your repo typically only has the **RedisEnterpriseCluster** CR (e.g. rec.yaml with `nodes: 3`).
- If Argo CD syncs an app that includes a **StatefulSet** for the REC with **replicas: 1**, it could overwrite the operator’s StatefulSet and prevent rec-1/rec-2. In that case, either remove the StatefulSet from Git or add **ignoreDifferences** so Argo CD does not change **replicas** (and let the operator control it).
- For the **RedisEnterpriseCluster** CR, add **ignoreDifferences** on **status** so Argo CD doesn’t fight the operator’s status updates (see your REC/Argo CD docs). That doesn’t create rec-1/rec-2 by itself but avoids sync issues.

---

## 4. Resource quotas and PVCs

If the **StatefulSet** already has **replicas: 3** but you only see rec-0:

- **rec-1 / rec-2 Pending** → Open each pod and check **Events** and **Conditions**:
  - **PVC** not bound (e.g. WaitForFirstConsumer, or storage quota).
  - **CPU/memory** quota in the namespace exhausted.
  - **Node selector / taints** so no node can schedule rec-1/rec-2.

Fix quotas, storage, or scheduling so rec-1 and rec-2 can be scheduled and start.

---

## 5. Summary

| Situation | Action |
|-----------|--------|
| rec-services-rigger logs: timeout to rec:9443 | Fix NetworkPolicy and connectivity (SOLUTION-rec-9443-timeout.md), then restart rec-services-rigger; wait and recheck for rec-1/rec-2. |
| StatefulSet replicas = 1 | Operator is likely waiting for cluster/API readiness; fix rec:9443 and wait, or check operator logs. |
| StatefulSet replicas = 3 but only rec-0 exists | rec-1/rec-2 are likely Pending; check pod Events and fix PVC/scheduling/resources. |
| Argo CD manages a StatefulSet for REC with replicas: 1 | Remove it from Git or use ignoreDifferences so the operator controls replicas. |

In most cases, **fixing the rec:9443 timeout** and letting the operator proceed is what allows rec-1 and rec-2 to be created.
