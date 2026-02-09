# Solution: "RS API is not available" / rec:9443 timeout (OpenShift UI)

Use this when **rec-services** or **redis-enterprise-operator** log:
- `RS API is not available: Get "https://rec:9443/v1/nodes": context deadline exceeded (Client.Timeout)`
- `get https://rec:9443/v1/nodes: context deadline exceeded`

---

## 1. Add the Network Policies (fix rec:9443 access)

You need **two** Network Policies in the **same project** where your REC, service **rec**, and rec-services/operator run.

1. In the OpenShift UI, go to your project (e.g. **bai32-baipi-gateway-baipi-gateway-dev-01**).
2. Open **Networking** → **Network Policies**.
3. Click **Create NetworkPolicy**.
4. Choose **Form view** or **YAML view**.
5. Create the **first** policy from the file **redis-enterprise-network-policy.yaml** (the block named **redis-enterprise-allow**): copy the YAML for that policy, paste it into the editor, and set **Namespace** to your project name. Click **Create**.
6. Create the **second** policy (the block named **rec-allow-9443**) the same way: copy its YAML, paste, set **Namespace** to your project, then **Create**.

Both policies must be in the project where service **rec** and the rec-services/operator pods run. The second policy selects REC pods with **app=redis-enterprise** and **redis.io/cluster=rec** (same as your service **rec**) and allows traffic on port 9443 from the operator and rec-services.

---

## 2. Check that service **rec** has endpoints

1. Go to **Networking** → **Services**.
2. Open the service **rec**.
3. Check the **Endpoints** or **Pods** tab: there should be at least one pod (e.g. rec-0) listed. If the list is empty, no REC pod is Ready yet — fix pod startup (storage, image, memory, or SCC), then the service will get endpoints and rec:9443 will become reachable.

---

## 3. Check that REC pods are Running and Ready

1. Go to **Workloads** → **Pods**.
2. Filter or find pods whose names start with **rec-** (e.g. rec-0, rec-1).
3. Each should show **Running** and **Ready**. If any are not Ready or are CrashLoopBackOff, fix pod startup; port 9443 is only available after the REC node has finished bootstrapping.

---

## 4. If the error is still there

**A. Restart rec-services (and optionally the operator)** so they retry with the new policy:

1. Go to **Workloads** → **Pods** (or **Deployments** / **StatefulSets**).
2. Find the **rec-services** pod (or the workload that runs it).
3. Open it and use **Actions** → **Restart** (or delete the pod so it is recreated). Do the same for **redis-enterprise-operator** if it also shows the error.

**B. Test without Network Policies** (to confirm policy was the cause):

1. Go to **Networking** → **Network Policies**.
2. Delete **redis-enterprise-allow** and **rec-allow-9443**.
3. Watch the rec-services (and operator) logs. If "RS API is not available" **stops**, the problem was policy — recreate both policies from the YAML file (Step 1).
4. If the error **continues** after deleting the policies, the cause is not policy (e.g. REC not ready or service not resolving). Recreate the policies and focus on Steps 2–3 and REC bootstrap.

---

## 5. Summary

Add both Network Policies in the REC project so the operator and rec-services can reach rec:9443. In the UI, confirm that service **rec** has endpoints and that REC pods (rec-0, …) are Running and Ready. If the error persists, restart rec-services (and the operator) and, if needed, temporarily remove the policies to confirm they were the cause, then add them again.
