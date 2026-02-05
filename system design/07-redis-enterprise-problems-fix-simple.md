# Redis Enterprise — Fix Problems the Simple Way

This page explains how to fix the errors you see when deploying Redis Enterprise (REC and REDB). Everything is in plain steps.

---

## What errors are we fixing?

1. **"rec not found"** — Argo CD says the admission webhook denied the request because it can’t find the cluster "rec".
2. **"The object has been modified"** — Argo CD and the operator are both trying to change the REC and they conflict.
3. **"Pod rec-0 not found"** or **"Waiting for first pod to bootstrap"** — The first Redis pod never starts or never becomes ready.
4. **"ConfigMap rec-bulletin-board not found"** — The operator keeps saying it can’t find or update the ConfigMap `rec-bulletin-board`.
5. **REC stuck in Progressing in Argo CD — REDB never created** — In Argo CD the REC stays "Progressing" (never "Healthy"), and the database (REDB) never gets created. The errors you see are in the REC pods or the operator, not in the Argo CD app pod.

---

## Fix 1: "rec not found" (admission webhook)

**What it means:** You are creating the database (REDB) before the cluster (REC) exists. The webhook checks "does the cluster exist?" and says no.

**What to do:**

1. **Apply in the right order.**  
   The cluster (REC) must be created first. The database (REDB) second.

2. **Use sync waves so Argo CD does that for you.**  
   In your REC YAML, add under `metadata`:
   ```yaml
   annotations:
     argocd.argoproj.io/sync-wave: "0"
   ```
   In your REDB YAML, add under `metadata`:
   ```yaml
   annotations:
     argocd.argoproj.io/sync-wave: "1"
   ```
   So: REC = wave 0 (first), REDB = wave 1 (second).

3. **Same namespace.**  
   REC and REDB must be in the **same** namespace as the Redis Enterprise operator. In Argo CD, set the app **Destination → Namespace** to that namespace (e.g. `redis-enterprise`).

4. **If it still fails:** Sync once (REC is created). Wait until the REC is ready. Then sync again (REDB is created).

---

## Fix 2: "The object has been modified"

**What it means:** Argo CD keeps applying your REC from Git. The operator also updates the REC (e.g. status). They overwrite each other and you get a conflict.

**What to do:**

1. **Tell Argo CD to ignore the REC’s status.**  
   So Argo CD won’t overwrite what the operator wrote.

2. **Where to set it — two ways:**

   **Option A — In the Application YAML file**  
   Open the file that defines your Argo CD Application (the one that deploys Redis). Add `ignoreDifferences` **inside** `spec:`, at the **same level** as `source`, `destination`, and `syncPolicy`. Example:

   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: redis-enterprise
     namespace: argocd
   spec:
     project: default
     ignoreDifferences:                    # <-- ADD HERE (same level as source, destination)
       - group: app.redislabs.com
         kind: RedisEnterpriseCluster
         jqPathExpressions:
           - .status
     source:
       repoURL: https://github.com/...
       path: ...
     destination:
       server: https://kubernetes.default.svc
       namespace: redis-enterprise
     syncPolicy:
       ...
   ```

   So: **exactly under `spec:`**, **before or after** `source` (same indentation as `source`).

   **Option B — In the Argo CD UI**  
   1. Open Argo CD in the browser.  
   2. Click your Redis app (the one that deploys REC/REDB).  
   3. Click **App Details** (or the three dots → **Application Details**).  
   4. Find **Diffing Customization** (or **Ignore Differences**).  
   5. Click **Add** (or **Add Item**).  
   6. Fill in: **Group** = `app.redislabs.com`, **Kind** = `RedisEnterpriseCluster`, **JQ Path Expression** = `.status` (one entry).  
   7. Save.

3. **If you use a Kustomize overlay or Helm for the Application:**  
   Add the same `ignoreDifferences` block under `spec` in the Application manifest that points at your Redis resources (the same Application that has `source` and `destination` for Redis).

4. **Optional:** Turn off **Auto-Sync** for this app for a while. Sync once by hand. When the REC is healthy, turn Auto-Sync back on.

---

## Fix 3: "Pod rec-0 not found" / "Waiting for first pod to bootstrap"

**What it means:** The operator created a StatefulSet for the REC but the first pod (`rec-0`) doesn’t exist or never becomes ready. So the operator keeps waiting.

**What to do (step by step):**

**Step A — See what’s wrong**

Use your real namespace name instead of `YOUR_NAMESPACE`:

```bash
kubectl get rec,sts,pods,pvc -n YOUR_NAMESPACE
kubectl get events -n YOUR_NAMESPACE --sort-by='.lastTimestamp' | tail -30
```

Look at the output:

- **No StatefulSet `rec`?** The operator didn’t create it yet. Fix the "object has been modified" (Fix 2) and wait, or check operator logs.
- **StatefulSet there but no pod?** Pods are not being created. Check **events** for "FailedScheduling" or similar.
- **Pod there but not Running?** Run:  
  `kubectl describe pod rec-0 -n YOUR_NAMESPACE`  
  and look at **Events** at the bottom.

**Step B — Fix the most common causes**

| What you see | What it usually is | What to do |
|--------------|--------------------|------------|
| PVC "Pending" | No storage or wrong storage class | Set a `storageClassName` in the REC that exists in the cluster, or create a default StorageClass. |
| "ImagePullBackOff" | Cannot pull the image | You need a pull secret for the Red Hat registry. Create the secret in the namespace and add it to the REC (see Step C below). |
| "OOMKilled" or "CrashLoopBackOff" | Not enough memory | In the REC, increase `redisEnterpriseNodeResources` (e.g. memory at least 4Gi, cpu at least 2). |
| OpenShift: pod not allowed to run | Security (SCC) | Use the Redis Enterprise SCC for the REC’s service account (see Redis/OpenShift docs). |

**Step C — Red Hat registry: create pull secret (if you use Red Hat images)**

If your REC uses images from `registry.connect.redhat.com`, create a secret so the pod can pull:

```bash
kubectl create secret docker-registry redhat-pull-secret \
  --docker-server=registry.connect.redhat.com \
  --docker-username=YOUR_REDHAT_USER \
  --docker-password=YOUR_REDHAT_PASSWORD \
  -n YOUR_NAMESPACE
```

Then either:

- Add this secret to the REC spec: `pullSecrets: [{ name: redhat-pull-secret }]`, or  
- Patch the service account used by the REC:  
  `kubectl patch serviceaccount default -n YOUR_NAMESPACE -p '{"imagePullSecrets":[{"name":"redhat-pull-secret"}]}'`  
  (use the correct service account name if it’s not `default`).

---

## Fix 4: "ConfigMap rec-bulletin-board not found"

**What it means:** The Redis Enterprise operator uses a ConfigMap named `rec-bulletin-board` (your REC name + `-bulletin-board`) to coordinate the cluster. The operator is supposed to create this ConfigMap when it sets up the REC. If you see "Failed to retrieve bulletin board" or "Failed to update bulletin board: ConfigMap rec-bulletin-board not found", that ConfigMap is missing and the operator is stuck trying to use it.

**Why it’s missing:** Often the operator never got to create it because:

- Argo CD and the operator were conflicting ("object has been modified"), so the operator couldn’t finish its setup.
- The operator doesn’t have permission to create ConfigMaps in that namespace (RBAC).
- Something deleted the ConfigMap after the operator created it.

**What to do:**

1. **Fix the conflict first (Fix 2).**  
   Add **ignoreDifferences** for the REC’s `.status` on your Argo CD Application and optionally disable Auto-Sync. That lets the operator run without being overwritten by GitOps.

2. **Check if the ConfigMap exists.**  
   Use the namespace where your REC lives (replace `YOUR_NAMESPACE`):
   ```bash
   kubectl get configmap rec-bulletin-board -n YOUR_NAMESPACE
   ```
   If it doesn’t exist, the operator hasn’t created it yet or couldn’t create it.

3. **Check operator permissions.**  
   The Redis Enterprise operator needs to create ConfigMaps in the same namespace as the REC. If you installed the operator with Helm/OLM in that namespace, it usually has a Role that allows this. If you see RBAC errors in the operator logs, fix the Role/RoleBinding so the operator can create and update ConfigMaps (and other resources it needs).

4. **Let the operator run without conflict.**  
   Disable Auto-Sync for the Redis app. Sync once so the REC is applied. Don’t sync again for a few minutes. Watch the operator create the StatefulSet, ConfigMaps, and pods. Check again:
   ```bash
   kubectl get configmap -n YOUR_NAMESPACE | grep rec
   kubectl get rec,sts,pods -n YOUR_NAMESPACE
   ```
   If the operator can run without conflict, it should create `rec-bulletin-board` and then the rest.

5. **Last resort: delete the REC and re-apply (only if safe).**  
   If there is no important data in this REC and you’ve fixed ignoreDifferences and RBAC, you can delete the REC and let the operator recreate everything:
   ```bash
   kubectl delete rec rec -n YOUR_NAMESPACE
   ```
   Then sync again from Argo CD (or apply your REC YAML again). The operator will create the REC again and, this time, should create `rec-bulletin-board` and the cluster. Only do this if you don’t need to keep the current cluster or its data.

**Summary:** The "rec-bulletin-board not found" message usually means the operator couldn’t finish setting up the REC. Fix the "object has been modified" conflict (ignoreDifferences, disable auto-sync), check RBAC, then let the operator run; it should create the ConfigMap. If not, delete the REC and re-apply only if safe.

**Deep dive:** For a full explanation of what the bulletin board ConfigMap is, why it goes missing, and a step-by-step fix (including RBAC checks and prune), see [09-redis-enterprise-rec-bulletin-board-deep-dive.md](09-redis-enterprise-rec-bulletin-board-deep-dive.md).

---

## Fix 5: REC stuck in Progressing in Argo CD — REDB never created

**What it means:** In the Argo CD UI, the **REC** (Redis Enterprise Cluster) never becomes "Healthy"; it stays **Progressing**. Because of that, the **REDB** (database) either never gets created or stays pending. The errors you see are in the **REC pods** or in the **Redis Enterprise operator** logs, not in the Argo CD application pod.

**Why it happens:** Argo CD marks the REC as "Healthy" only when the REC resource (and sometimes the things it creates) are ready. The REC becomes ready only when the **operator** has finished setting up the cluster (StatefulSet, pods like `rec-0`, ConfigMap `rec-bulletin-board`, etc.). If the operator is stuck (conflict with Argo CD, missing ConfigMap, pods not starting), the REC never becomes ready, so Argo CD keeps showing Progressing and the REDB can’t be created.

**What to do (in order):**

**Step 1 — Stop Argo CD from fighting the operator**

1. Add **ignoreDifferences** for the REC’s `.status` on your Argo CD Application (see Fix 2 for where exactly).
2. **Disable Auto-Sync** for the Redis app in Argo CD (App Details → uncheck Auto-Sync). So Argo CD won’t keep reapplying and conflicting with the operator.
3. **Sync once** (manual Sync). Then don’t sync again for several minutes.

**Step 2 — Fix why the REC never becomes ready (check REC pods and operator)**

Use the namespace where your REC lives (replace `YOUR_NAMESPACE`):

```bash
export NS=YOUR_NAMESPACE

# REC, StatefulSet, REC pods (rec-0, rec-1, rec-2), PVCs
kubectl get rec,sts,pods,pvc -n $NS

# Recent events (scheduling, image pull, PVC, OOM)
kubectl get events -n $NS --sort-by='.lastTimestamp' | tail -40
```

- **No StatefulSet `rec` or no pods?** The operator didn’t create them yet. Check **operator logs** (the redis-enterprise-operator pod). Fix the "object has been modified" and "rec-bulletin-board not found" issues (Fix 2 and Fix 4) so the operator can create the StatefulSet and ConfigMap.
- **Pods exist but not Running?** Run `kubectl describe pod rec-0 -n $NS` and look at **Events**. Fix **PVC** (storage class), **image pull** (pull secret for Red Hat registry), or **memory** (increase `redisEnterpriseNodeResources` in the REC). On OpenShift, fix **SCC** if the pod is blocked by security.
- **Operator logs show "rec-bulletin-board not found"?** Follow Fix 4: after adding ignoreDifferences and disabling auto-sync, let the operator run; it should create the ConfigMap. If not, check RBAC.

**Step 3 — Let the operator finish**

After you’ve added ignoreDifferences and disabled auto-sync:

1. Don’t sync the Redis app again for 5–10 minutes.
2. Watch the operator create (or update) the StatefulSet, ConfigMaps, and pods. Check:
   ```bash
   kubectl get rec,sts,pods,configmap -n $NS | grep rec
   ```
3. Wait until **all REC pods** (e.g. `rec-0`, `rec-1`, `rec-2`) are **Running** and ready. The operator will then mark the REC as ready and Argo CD should eventually show the REC as **Healthy** (or at least the cluster will be usable).

**Step 4 — If REC is still stuck Progressing in Argo CD**

Argo CD might be using a health check that never passes for the REC. You can:

- **Option A:** Ignore REC health in Argo CD so the app doesn’t stay "Progressing" forever. In the Application, add under `spec`:
  ```yaml
  ignoreDifferences:
    - group: app.redislabs.com
      kind: RedisEnterpriseCluster
      jqPathExpressions:
        - .status
  ```
  (You should already have this.) Then add a **resource custom health check** or tell Argo CD to not treat REC as "Progressing" forever — or just wait until the REC’s status in the cluster is actually ready; some Argo CD versions then show Healthy.

- **Option B:** Ensure the REC is really ready in the cluster. Run:
  ```bash
  kubectl get rec rec -n $NS -o yaml
  ```
  Look at `status`. When the operator has finished, there is usually a status indicating the cluster is ready. Until then, keep fixing operator/REC pod issues (Step 2).

**Step 5 — Create the REDB only after the REC is ready**

- The **REDB** (database) should be created only after the REC is ready (sync wave 1; see Fix 1). If the REC was stuck Progressing, the REDB may not have been created or may have failed. Once the REC is healthy (pods Running, operator happy):
  1. Turn Auto-Sync back on if you want, or sync once manually.
  2. The REDB (wave 1) will be created and should succeed now that the REC exists and is ready.

**Summary:** REC stuck in Progressing = the cluster (REC) never became ready. Fix the conflict (ignoreDifferences, disable auto-sync), then fix why the operator/REC pods are stuck (ConfigMap, PVC, image, memory, RBAC). Once the REC pods are Running and the operator has finished, the REC becomes ready and the REDB can be created.

---

## Fix 6: rec-services-rigger "get https://rec:9443/v1/nodes: context deadline exceeded"

**What it means:** The **rec-services-rigger** pod (Services Manager) is calling the REC REST API at **https://rec:9443/v1/nodes** and the request is timing out. So you see "context deadline exceeded" or "Client.Timeout exceeded while awaiting headers" in the services-rigger logs.

**Why it happens:** Usually (1) the Service **rec** has no endpoints (REC pods not Ready yet), (2) REC pods are not listening on 9443 yet (bootstrap not finished), or (3) a **NetworkPolicy** is blocking rec-services-rigger from reaching the REC pods.

**What to do:** Check that the Service **rec** has endpoints (`kubectl get endpoints rec -n YOUR_NAMESPACE`), that REC pods (rec-0, …) are Running and Ready, and that your NetworkPolicy allows traffic **from** rec-services-rigger **to** REC pods (e.g. add an ingress rule for pods with label `app.kubernetes.io/component: services-rigger` or `app: rec`). Then retry or wait for bootstrap to complete.

**Deep dive:** For step-by-step checks (Service, endpoints, REC pods, NetworkPolicy, connectivity test), see [10-redis-enterprise-rec-services-rigger-9443-timeout-deep-dive.md](10-redis-enterprise-rec-services-rigger-9443-timeout-deep-dive.md).

---

## Checklist: do these in order

1. REC and REDB in the **same namespace** as the Redis Enterprise operator.  
2. **Sync waves:** REC = 0, REDB = 1.  
3. **ignoreDifferences** for REC `.status` on the Argo CD Application.  
4. (Optional) **Disable Auto-Sync** until the REC is healthy.  
5. Run **kubectl get rec,sts,pods,pvc** and **events** in that namespace; fix **PVC**, **image pull**, or **memory** if needed.  
6. If you use Red Hat images, create the **pull secret** and add it to the REC or service account.  
7. **Sync** (or sync again). Wait for `rec-0` to be Running, then the REDB can be created.  
8. If you see **"rec-bulletin-board not found"** → Fix the conflict (ignoreDifferences), check RBAC, then let the operator run so it can create the ConfigMap; see Fix 4.  
9. If **REC is stuck Progressing and REDB never created** → Add ignoreDifferences, disable auto-sync, fix REC pods/operator (ConfigMap, PVC, image, memory), then wait for REC to become ready; see Fix 5.

---

## One sentence per fix

- **"rec not found"** → Create REC first, REDB second (use sync waves 0 and 1), same namespace as operator.  
- **"Object has been modified"** → Add ignoreDifferences for REC `.status` in the Argo CD app; optionally disable auto-sync for a while.  
- **"rec-0 not found" / "Waiting for first pod"** → Check pods/PVC/events in the namespace; fix storage, image pull secret, or memory; on OpenShift fix SCC if needed.  
- **"ConfigMap rec-bulletin-board not found"** → Fix the conflict (ignoreDifferences) and RBAC so the operator can create the ConfigMap; if needed, delete the REC and re-apply (only if safe).  
- **REC stuck Progressing, REDB never created** → Add ignoreDifferences, disable auto-sync, fix REC pods and operator (ConfigMap, PVC, image, memory), wait for REC to become ready, then REDB can be created (Fix 5).
- **rec-services-rigger "get https://rec:9443/v1/nodes: context deadline exceeded"** → Ensure Service **rec** has endpoints, REC pods are Ready, and NetworkPolicy allows rec-services-rigger → rec; see [10-redis-enterprise-rec-services-rigger-9443-timeout-deep-dive.md](10-redis-enterprise-rec-services-rigger-9443-timeout-deep-dive.md).
