# Redis Enterprise — Fix Problems the Simple Way

This page explains how to fix the errors you see when deploying Redis Enterprise (REC and REDB). Everything is in plain steps.

---

## What errors are we fixing?

1. **"rec not found"** — Argo CD says the admission webhook denied the request because it can’t find the cluster "rec".
2. **"The object has been modified"** — Argo CD and the operator are both trying to change the REC and they conflict.
3. **"Pod rec-0 not found"** or **"Waiting for first pod to bootstrap"** — The first Redis pod never starts or never becomes ready.
4. **"ConfigMap rec-bulletin-board not found"** — The operator keeps saying it can’t find or update the ConfigMap `rec-bulletin-board`.

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

2. **Where to set it:**  
   Open your Argo CD Application (the one that deploys Redis). Add this under `spec:`:

   ```yaml
   ignoreDifferences:
     - group: app.redislabs.com
       kind: RedisEnterpriseCluster
       jqPathExpressions:
         - .status
   ```

3. **In the Argo CD UI:**  
   Open the app → **App Details** → **Diffing Customization** → add a difference: Group `app.redislabs.com`, Kind `RedisEnterpriseCluster`, and ignore path `.status`.

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

---

## One sentence per fix

- **"rec not found"** → Create REC first, REDB second (use sync waves 0 and 1), same namespace as operator.  
- **"Object has been modified"** → Add ignoreDifferences for REC `.status` in the Argo CD app; optionally disable auto-sync for a while.  
- **"rec-0 not found" / "Waiting for first pod"** → Check pods/PVC/events in the namespace; fix storage, image pull secret, or memory; on OpenShift fix SCC if needed.  
- **"ConfigMap rec-bulletin-board not found"** → Fix the conflict (ignoreDifferences) and RBAC so the operator can create the ConfigMap; if needed, delete the REC and re-apply (only if safe).
