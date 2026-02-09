# Step-by-Step Troubleshooting: "RS API is not available" (OpenShift UI)

Follow these steps **in order** to find and fix why rec-services cannot reach rec:9443.

---

## Step 1: Check Service "rec" has endpoints

1. Go to **Networking** → **Services**.
2. Find and open the service named **rec**.
3. Look at the **Endpoints** tab or **Pods** tab.
   - ✅ **If you see pod names** (e.g. rec-0, rec-1): Service has endpoints → go to Step 2.
   - ❌ **If the list is empty**: No REC pods are Ready → go to **"Fix: REC pods not Ready"** below.

---

## Step 2: Check REC pods are Running and Ready

1. Go to **Workloads** → **Pods**.
2. Find pods whose names start with **rec-** (e.g. rec-0, rec-1, rec-2).
3. Check each pod:
   - ✅ **Status = Running** and **Ready = 1/1** (or 1/1): Pod is ready → go to Step 3.
   - ❌ **Status = CrashLoopBackOff** or **Ready = 0/1**: Pod is not ready → go to **"Fix: REC pods not Ready"** below.

---

## Step 3: Check what labels REC pods actually have

**This is critical** — the NetworkPolicy must match these labels.

1. Go to **Workloads** → **Pods**.
2. Open one of the REC pods (e.g. **rec-0**).
3. Go to the **Details** tab or **YAML** tab.
4. Find the **Labels** section (or look for `metadata.labels` in YAML).
5. **Write down** the label keys and values you see. Common ones:
   - `app=redis-enterprise`
   - `redis.io/cluster=rec`
   - `redis.io/role=node`
   - Or maybe `app=rec` or `app.kubernetes.io/name=redis-enterprise`

**Note these labels** — you'll need them in Step 5.

---

## Step 4: Check what labels rec-services pod has

1. Go to **Workloads** → **Pods**.
2. Find the pod that runs **rec-services** (name might be like `rec-services-...` or `rec-services-rigger-...`).
3. Open it and check **Labels** (Details or YAML tab).
4. **Write down** the labels (e.g. `app.kubernetes.io/component=services-rigger`, `app=rec`, etc.).

**Note these labels** — you'll need them in Step 5.

---

## Step 5: Check Network Policies are applied and match correctly

1. Go to **Networking** → **Network Policies**.
2. Check if you see:
   - **redis-enterprise-allow**
   - **rec-allow-9443**

**If policies are missing:**
- Create them from the YAML file (see SOLUTION-rec-9443-timeout.md Step 1).

**If policies exist:**
- Open **rec-allow-9443**.
- Go to **YAML** tab.
- Check the **podSelector.matchLabels** section:
  - It should match the labels you wrote down in **Step 3** (REC pod labels).
  - If it says `app: rec` but your REC pods have `app: redis-enterprise`, that's the problem → go to **"Fix: Update NetworkPolicy labels"** below.
- Check the **ingress** section:
  - There should be rules that allow from pods matching the labels you wrote down in **Step 4** (rec-services labels).
  - If rec-services has `app.kubernetes.io/component=services-rigger` but the policy doesn't allow from that label, that's the problem → go to **"Fix: Update NetworkPolicy ingress rules"** below.

---

## Step 6: Check if there's a default-deny policy blocking everything

1. Go to **Networking** → **Network Policies**.
2. Look for any policy with a name like **default-deny** or **deny-all** or similar.
3. If you see one:
   - Open it and check if it selects REC pods (same labels as Step 3).
   - If it does, you need to either:
     - **Delete it** (if safe), OR
     - **Add an exception** in that policy to allow traffic from rec-services/operator to REC pods on port 9443.

---

## Step 7: Check if operator/rec-services are in a different namespace

1. Check which **project/namespace** your REC pods are in (look at the top of the page or in pod details).
2. Check which **project/namespace** the **rec-services** pod is in.
3. Check which **project/namespace** the **redis-enterprise-operator** pod is in.
4. **If they're in different namespaces:**
   - NetworkPolicies with `podSelector: {}` only match pods in the **same namespace**.
   - You need to add a rule that allows from the operator's namespace (using `namespaceSelector`). See **"Fix: Operator in different namespace"** below.

---

## Fix: REC pods not Ready

If REC pods are not Running/Ready:

1. Go to **Workloads** → **Pods**.
2. Open a REC pod that's not ready (e.g. rec-0).
3. Check the **Events** tab for errors:
   - **PVC/PersistentVolumeClaim**: Storage issue → fix storage class or PVC.
   - **ImagePullBackOff**: Image pull issue → add pull secret or fix image.
   - **OOMKilled**: Out of memory → increase memory limits in REC spec.
   - **SCC/SecurityContextConstraints**: On OpenShift, REC pods might need a specific SCC → grant `redis-enterprise-scc-v2` to the REC's service account.
4. Fix the issue, wait for pods to become Ready, then retry.

---

## Fix: Update NetworkPolicy labels

If the NetworkPolicy `podSelector` doesn't match your REC pod labels:

1. Go to **Networking** → **Network Policies**.
2. Open **rec-allow-9443**.
3. Click **Edit NetworkPolicy** (or **Actions** → **Edit YAML**).
4. In the **podSelector.matchLabels** section, change it to match your REC pod labels from Step 3:
   ```yaml
   podSelector:
     matchLabels:
       app: redis-enterprise        # Use the label your REC pods have
       redis.io/cluster: rec        # Use the label your REC pods have
   ```
5. Click **Save**.

---

## Fix: Update NetworkPolicy ingress rules

If the NetworkPolicy doesn't allow from rec-services labels:

1. Go to **Networking** → **Network Policies**.
2. Open **rec-allow-9443**.
3. Click **Edit NetworkPolicy**.
4. In the **ingress** section, add a rule that allows from rec-services pod labels (from Step 4):
   ```yaml
   ingress:
     - from:
         - podSelector:
             matchLabels:
               app.kubernetes.io/component: services-rigger   # Use rec-services labels from Step 4
       ports:
         - protocol: TCP
           port: 9443
   ```
5. Click **Save**.

---

## Fix: Operator in different namespace

If the operator or rec-services are in a different namespace:

1. Go to **Networking** → **Network Policies**.
2. Open **rec-allow-9443**.
3. Click **Edit NetworkPolicy**.
4. Add an ingress rule that allows from the operator's namespace:
   ```yaml
   ingress:
     - from:
         - namespaceSelector:
             matchLabels:
               kubernetes.io/metadata.name: <operator-namespace>   # Replace with actual namespace
         - podSelector:
             matchLabels:
               app.kubernetes.io/name: redis-enterprise-operator
       ports:
         - protocol: TCP
           port: 9443
   ```
5. Click **Save**.

---

## Quick test: Temporarily remove Network Policies

To confirm if NetworkPolicy is the cause:

1. Go to **Networking** → **Network Policies**.
2. Delete **redis-enterprise-allow** and **rec-allow-9443**.
3. Watch the rec-services logs (Workloads → Pods → rec-services → Logs).
4. **If "RS API is not available" stops**: The problem was NetworkPolicy → recreate both policies with correct labels (Steps 3–5).
5. **If the error continues**: The problem is not NetworkPolicy → focus on REC pods not Ready (Step 2) or Service rec has no endpoints (Step 1).

---

## What to share if you need help

If you're still stuck, check and share:

1. **Service rec Endpoints**: Does it show pod names? (Step 1)
2. **REC pods Status**: Are they Running and Ready? (Step 2)
3. **REC pod labels**: What labels do rec-0 pods have? (Step 3)
4. **rec-services pod labels**: What labels does rec-services have? (Step 4)
5. **Network Policies**: Do redis-enterprise-allow and rec-allow-9443 exist? What are their podSelector.matchLabels? (Step 5)
6. **Namespaces**: Are REC, rec-services, and operator all in the same project/namespace? (Step 7)
