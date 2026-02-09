# Fix Now: Update NetworkPolicy Labels (OpenShift UI)

## The Problem

Your NetworkPolicy `redis-enterprise-allow` uses the wrong labels:
- It selects pods with `app.kubernetes.io/name: redis-enterprise`
- But your REC pods (rec-0) have `app: redis-enterprise` (different label key!)

So the policy doesn't apply to rec-0, and rec-services-rigger can't reach rec:9443.

---

## The Fix (Do This Now)

### Step 1: Edit the NetworkPolicy `redis-enterprise-allow`

1. Go to **Networking** → **Network Policies**.
2. Find and open **redis-enterprise-allow**.
3. Click **Edit NetworkPolicy** (or **Actions** → **Edit YAML**).
4. In the **YAML** tab, find the `podSelector.matchLabels` section (around line 35).
5. Change:
   ```yaml
   podSelector:
     matchLabels:
       app.kubernetes.io/name: redis-enterprise
   ```
   To:
   ```yaml
   podSelector:
     matchLabels:
       app: redis-enterprise
   ```

6. Find the `ingress` section (around line 40).
7. Change the first `from` rule (around line 42-45) from:
   ```yaml
   - from:
       - podSelector:
           matchLabels:
             app.kubernetes.io/name: redis-enterprise
   ```
   To:
   ```yaml
   - from:
       - podSelector:
           matchLabels:
             app: redis-enterprise
   ```

8. Find the rec-services-rigger rules (around line 55-63).
9. Change them to:
   ```yaml
   - from:
       - podSelector:
           matchLabels:
             app: redis-enterprise
             redis.io/role: services-rigger
   - from:
       - podSelector:
           matchLabels:
             app: redis-enterprise
             redis.io/cluster: rec
   ```

10. Find the `egress` section (around line 80).
11. Change the first `to` rule from `app.kubernetes.io/name: redis-enterprise` to `app: redis-enterprise`.

12. Click **Save**.

---

### Step 2: Verify the second policy `rec-allow-9443`

1. Go to **Networking** → **Network Policies**.
2. Open **rec-allow-9443**.
3. Check the **YAML** tab.
4. The `podSelector.matchLabels` should be:
   ```yaml
   podSelector:
     matchLabels:
       app: redis-enterprise
       redis.io/cluster: rec
   ```
   ✅ This is already correct — it matches your rec-0 pods!

5. The `ingress` section should have:
   ```yaml
   - from:
       - podSelector: {}
   ```
   ✅ This allows from ALL pods in the namespace, so rec-services-rigger is already allowed.

---

### Step 3: Restart rec-services-rigger

1. Go to **Workloads** → **Pods**.
2. Find the **rec-services-rigger** pod (name like `rec-services-rigger-...`).
3. Open it and click **Actions** → **Delete** (or **Restart** if available).
4. Wait for it to restart.
5. Check the **Logs** tab — the "RS API is not available" error should stop.

---

## Summary

The NetworkPolicy `redis-enterprise-allow` was using `app.kubernetes.io/name: redis-enterprise` but your pods use `app: redis-enterprise`. After updating the policy to match your actual pod labels and restarting rec-services-rigger, the error should be fixed.
